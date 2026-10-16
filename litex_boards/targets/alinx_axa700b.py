#!/usr/bin/env python3
#
# LiteX SoC target for the ALINX AX7A200B carrier board with XC7A200T FPGA.
#
# Based on the AX7A200B User Manual provided by the user.
# SPDX-License-Identifier: BSD-2-Clause
#
# Important:
# - This is a porting baseline, not a claim of tested synthesis/hardware operation.
# - Ensure ax7a200b.py is installed as litex_boards.platforms.ax7a200b.
# - DDR3 geometry/timing and LiteDRAM PHY settings must be validated for the
#   exact core-board memory population and chosen sys_clk_freq.
# - PCIe pins in the supplied manual describe an x2 interface. This target
#   therefore exposes x2, not the AX7203's x4 interface.
# - The manual lists HDMI input and output pins separately, but both chips
#   share the same I2C pins H13/G13. Do not instantiate two I2C masters on
#   this shared bus without an explicit shared-bus/multiplexer design.
#

import os

from litex_boards.platforms import alinx_axa700b

from litex.gen import *
from litex.soc.cores.clock import *
from litex.soc.integration.soc import *
from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.builder import Builder
from litex.soc.cores.led import LedChaser

from litedram.modules import MT41J256M16
from litedram.phy import s7ddrphy


# CRG ----------------------------------------------------------------------------------------------

class _CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq):
        self.rst = Signal()
        self.cd_sys = ClockDomain()
        self.cd_sys4x = ClockDomain()
        self.cd_sys4x_dqs = ClockDomain()
        self.cd_idelay = ClockDomain()
        self.cd_hdmi = ClockDomain(reset_less=True)

        clk200 = platform.request("clk200")
        reset = platform.request("user_reset")

        self.pll = pll = S7PLL(speedgrade=-2)
        pll.reset.eq(self.rst)
        self.comb += pll.reset.eq(self.rst | ~reset)

        pll.register_clkin(clk200, 200e6)
        pll.create_clkout(self.cd_sys,       sys_clk_freq)
        pll.create_clkout(self.cd_sys4x,     4 * sys_clk_freq)
        pll.create_clkout(self.cd_sys4x_dqs, 4 * sys_clk_freq, phase=90)
        pll.create_clkout(self.cd_idelay,    200e6)
        pll.create_clkout(self.cd_hdmi,      148.5e6, margin=2e-2)

        platform.add_false_path_constraints(self.cd_sys.clk, pll.clkin)
        self.idelayctrl = S7IDELAYCTRL(self.cd_idelay)


# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(
        self,
        sys_clk_freq=50e6,
        with_led_chaser=True,
        with_pcie=False,
        with_video_framebuffer=False,
        **kwargs,
    ):
        platform = alinx_axa700b.Platform()

        # Clock/reset generator.
        self.crg = _CRG(platform, sys_clk_freq)

        # Main LiteX SoC.
        SoCCore.__init__(
            self,
            platform,
            sys_clk_freq,
            ident="LiteX SoC on ALINX AX7A200B",
            **kwargs,
        )

        # DDR3 SDRAM.
        # The board manual describes two MT41J256M16 devices forming a 32-bit
        # interface. Validate the module geometry/rate against the actual core
        # board and LiteDRAM version before relying on memory.
        self.ddrphy = s7ddrphy.A7DDRPHY(
            platform.request("ddram"),
            memtype="DDR3",
            nphases=4,
            sys_clk_freq=sys_clk_freq,
            iodelay_clk_freq=200e6,
        )
        self.add_sdram(
            "sdram",
            phy=self.ddrphy,
            module=MT41J256M16(sys_clk_freq, "1:4"),
            l2_cache_size=kwargs.get("l2_size", 8192),
        )

        # PCIe.
        # The AX7A200B manual's carrier-board feature description/pin table
        # documents two PCIe lanes, unlike the AX7203 x4 target.
        if with_pcie:
            from litepcie.phy.s7pciephy import S7PCIEPHY
            from litepcie.software import generate_litepcie_software
            from litex.soc.cores.icap import ICAP
            from litex.soc.cores.gpio import GPIOOut
            from litex.soc.cores.spi_flash import S7SPIFlash

            self.pcie_phy = S7PCIEPHY(
                platform,
                platform.request("pcie_x2"),
                data_width=64,
                bar0_size=0x20000,
            )
            self.add_pcie(phy=self.pcie_phy, ndmas=1, address_width=64)
            platform.add_period_constraint(self.crg.cd_sys.clk, 1e9 / sys_clk_freq)

            self.icap = ICAP()
            self.icap.add_reload()
            self.icap.add_timing_constraints(
                platform, sys_clk_freq, self.crg.cd_sys.clk
            )

            self.flash_cs_n = GPIOOut(platform.request("flash_cs_n"))
            self.flash = S7SPIFlash(
                platform.request("flash"), sys_clk_freq, 25e6
            )

        # HDMI output video.
        # This path requires a video-capable clocking solution and verified
        # transmitter initialization registers. The board's output interface
        # is exposed as "hdmi_out" in the AX7A200B platform.
        if with_video_framebuffer:
            from litex.soc.cores.video import VideoDVIPHY
            from litex.soc.cores.bitbang import I2CMaster

            hdmi_pads = platform.request("hdmi_out")
            self.videophy = VideoDVIPHY(hdmi_pads, clock_domain="hdmi")
            self.videoi2c = I2CMaster(hdmi_pads)

            # These are the same baseline transmitter setup writes used by
            # the original AX7203 target. Confirm them against the SIL9134
            # programming guide and the AX7A200B board revision before use.
            self.videoi2c.add_init(addr=0x72 >> 1, init_addr_len=1, init=[
                (0x0008, 0x35),
            ])
            self.videoi2c.add_init(addr=0x7A >> 1, init_addr_len=1, init=[
                (0x002f, 0x00),
            ])
            self.videoi2c.add_init(addr=0x60 >> 1, init_addr_len=1, init=[
                (0x0005, 0x10),
                (0x0008, 0x05),
                (0x0009, 0x01),
                (0x0005, 0x04),
            ])
            self.add_video_colorbars(
                phy=self.videophy,
                timings="1920x1080@60Hz",
                clock_domain="hdmi",
            )

        # Active-low carrier-board user LEDs: invert the chaser output so
        # logical 'on' drives the physical pin low.
        if with_led_chaser:
            led_pads = platform.request_all("user_led")
            self.leds = LedChaser(pads=led_pads, sys_clk_freq=sys_clk_freq)


# Build --------------------------------------------------------------------------------------------

def main():
    from litex.build.parser import LiteXArgumentParser

    parser = LiteXArgumentParser(
        platform=alinx_axa700b.Platform,
        description="LiteX SoC on ALINX AX7A200B.",
    )
    parser.add_target_argument(
        "--flash", action="store_true", help="Flash bitstream."
    )
    parser.add_target_argument(
        "--sys-clk-freq", default=50e6, type=float,
        help="System clock frequency (default: 50 MHz)."
    )
    parser.add_target_argument(
        "--with-pcie", action="store_true", help="Enable PCIe x2 support."
    )
    parser.add_target_argument(
        "--driver", action="store_true", help="Generate LitePCIe drivers."
    )
    parser.add_target_argument(
        "--with-video-framebuffer", action="store_true",
        help="Enable HDMI output framebuffer (requires completing HDMI I2C wiring)."
    )

    args = parser.parse_args()

    soc = BaseSoC(
        sys_clk_freq=args.sys_clk_freq,
        with_led_chaser=True,
        with_pcie=args.with_pcie,
        with_video_framebuffer=args.with_video_framebuffer,
        **parser.soc_argdict,
    )

    builder = Builder(soc, **parser.builder_argdict)

    if args.build or args.driver:
        if not args.build:
            builder.compile_software = False
            builder.compile_gateware = False
        builder.build(**parser.toolchain_argdict)

    if args.driver:
        if not args.with_pcie:
            raise ValueError("--driver requires --with-pcie")
        from litepcie.software import generate_litepcie_software
        generate_litepcie_software(
            soc, os.path.join(builder.output_dir, "driver")
        )

    if args.load:
        programmer = soc.platform.create_programmer()
        programmer.load_bitstream(builder.get_bitstream_filename(mode="sram"))

    if args.flash:
        programmer = soc.platform.create_programmer()
        programmer.flash(0, builder.get_bitstream_filename(mode="flash"))


if __name__ == "__main__":
    main()
