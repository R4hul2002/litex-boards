#
# AX7A200B LiteX platform definition
#
# Pin assignments transcribed from:
#   AX7A200B User Manual, Rev. 1.0
#   Core board: pages 10-16 (clocks, DDR3, QSPI)
#   Carrier board: pages 31-48 (Ethernet, SFP, PCIe, HDMI, SD, UART,
#                               EEPROM, expansion headers, keys, LEDs)
#
# SPDX-License-Identifier: BSD-2-Clause
#
# IMPORTANT:
# - This is a platform/pin definition, not a complete SoC design.
# - Verify against your exact board revision and the board's master XDC
#   before hardware use. The manual has a few inconsistent interface labels.
# - PCIe is defined as x2 based on the manual's feature description/pin table.
# - DDR3 pinout is included; DDR3 still needs a correctly configured LiteDRAM
#   PHY/controller for the exact memory geometry and timing.
#

from litex.build.generic_platform import *
from litex.build.xilinx import Xilinx7SeriesPlatform
from litex.build.openfpgaloader import OpenFPGALoader

import subprocess


_io = [
    # Core-board system clock: 200 MHz differential oscillator (manual p. 11).
    ("clk200", 0,
        Subsignal("p", Pins("R4"), IOStandard("DIFF_SSTL15")),
        Subsignal("n", Pins("T4"), IOStandard("DIFF_SSTL15")),
    ),

    # Core-board 125 MHz GTP reference clock (manual p. 11).
    # This is a transceiver reference clock, not a general fabric clock.
    ("gtp_clk125", 0,
        Subsignal("p", Pins("F6")),
        Subsignal("n", Pins("E6")),
    ),

    # Carrier-board USB-UART via CP2102GM (manual p. 40).
    ("serial", 0,
        Subsignal("rx", Pins("L14"), IOStandard("LVCMOS33")),
        Subsignal("tx", Pins("L15"), IOStandard("LVCMOS33")),
    ),

    # Carrier-board Gigabit Ethernet PHY JL2121, RGMII (manual pp. 30-31).
    ("eth_clocks", 0,
        Subsignal("tx", Pins("P15")),
        Subsignal("rx", Pins("V18")),
        IOStandard("LVCMOS33"),
    ),
    ("eth", 0,
        Subsignal("rst_n", Pins("R14"), IOStandard("LVCMOS33")),
        Subsignal("mdio",  Pins("P14"), IOStandard("LVCMOS33")),
        Subsignal("mdc",   Pins("N13"), IOStandard("LVCMOS33")),
        Subsignal("rx_ctl", Pins("R19"), IOStandard("LVCMOS33")),
        Subsignal("rx_data", Pins("P19 U18 U17 P17"), IOStandard("LVCMOS33")),
        Subsignal("tx_ctl", Pins("N17"), IOStandard("LVCMOS33")),
        Subsignal("tx_data", Pins("N14 P16 R17 R16"), IOStandard("LVCMOS33")),
    ),

    # PCI Express x2 (manual pp. 33-35).
    # Differential GTP signals are not assigned LVCMOS I/O standards.
    ("pcie_x2", 0,
        Subsignal("clk_p", Pins("F10")),
        Subsignal("clk_n", Pins("E10")),
        Subsignal("rx_p", Pins("D9 B10")),
        Subsignal("rx_n", Pins("C9 A10")),
        Subsignal("tx_p", Pins("D7 B6")),
        Subsignal("tx_n", Pins("C7 A6")),
    ),

    # Two SFP/GTP channels (manual pp. 32-33).
    ("sfp", 0,
        Subsignal("tx_p", Pins("B4")),
        Subsignal("tx_n", Pins("A4")),
        Subsignal("rx_p", Pins("B8")),
        Subsignal("rx_n", Pins("A8")),
        Subsignal("tx_disable", Pins("J15"), IOStandard("LVCMOS33")),
        Subsignal("los", Pins("H15"), IOStandard("LVCMOS33")),
    ),
    ("sfp", 1,
        Subsignal("tx_p", Pins("D5")),
        Subsignal("tx_n", Pins("C5")),
        Subsignal("rx_p", Pins("D11")),
        Subsignal("rx_n", Pins("C11")),
        Subsignal("tx_disable", Pins("H14"), IOStandard("LVCMOS33")),
        Subsignal("los", Pins("J14"), IOStandard("LVCMOS33")),
    ),

    # HDMI output via SIL9134 (manual pp. 35-36).
    # D[23:0] is the parallel pixel bus; chip initialization uses HDMI I2C.
    ("hdmi_out", 0,
        Subsignal("data", Pins(
            "V22 Y18 Y19 W19 W20 Y21 U21 T21 "
            "W21 W22 T20 AB18 AA18 AA19 AB20 AA20 "
            "AA21 AB22 AB21 W17 V17 V20 U20 V19"
        )),
        Subsignal("de", Pins("U22")),
        Subsignal("clk", Pins("Y22")),
        Subsignal("hsync", Pins("T18")),
        Subsignal("vsync", Pins("R18")),
        Subsignal("reset_n", Pins("Y17")),
        IOStandard("LVCMOS33"),
    ),

    # HDMI input via SIL9013 (manual pp. 37-38).
    ("hdmi_in", 0,
        Subsignal("data", Pins(
            "M20 N20 L21 M21 K19 H17 H18 N22 "
            "M22 K22 K21 J22 H22 H20 G20 M17 "
            "J16 G17 G18 G15 G16 J19 H19 J20"
        )),
        Subsignal("de", Pins("N19")),
        Subsignal("clk", Pins("K18")),
        Subsignal("hsync", Pins("N18")),
        Subsignal("vsync", Pins("M18")),
        Subsignal("reset_n", Pins("J21")),
        IOStandard("LVCMOS33"),
    ),

    # HDMI transmitter/receiver configuration I2C bus is shared (manual pp. 35-38).
    ("hdmi_i2c", 0,
        Subsignal("scl", Pins("H13")),
        Subsignal("sda", Pins("G13")),
        IOStandard("LVCMOS33"),
    ),

    # MicroSD socket, SD mode (manual p. 39). Pull-ups are on the board.
    ("sdcard", 0,
        Subsignal("clk", Pins("E13")),
        Subsignal("cmd", Pins("E14")),
        Subsignal("cd", Pins("C13")),
        Subsignal("data", Pins("D15 D14 F14 F13")),
        IOStandard("LVCMOS33"),
    ),

    # EEPROM 24LC04 and LM75 temperature sensor share this I2C bus
    # (manual pp. 41-42).
    ("i2c", 0,
        Subsignal("scl", Pins("M15")),
        Subsignal("sda", Pins("M16")),
        IOStandard("LVCMOS33"),
    ),

    # Carrier-board keys are active-low (manual p. 47).
    ("user_btn", 0, Pins("L19"), IOStandard("LVCMOS33")),
    ("user_btn", 1, Pins("L20"), IOStandard("LVCMOS33")),
    ("user_btn", 2, Pins("K17"), IOStandard("LVCMOS33")),
    ("user_btn", 3, Pins("J17"), IOStandard("LVCMOS33")),
    ("user_reset", 0, Pins("F15"), IOStandard("LVCMOS33")),

    # Carrier-board user LEDs are active-low (manual pp. 47-48).
    ("user_led", 0, Pins("L13"), IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("M13"), IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("K14"), IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("K13"), IOStandard("LVCMOS33")),

    # Core-board user LED (manual p. 17), active high per manual description.
    ("core_led", 0, Pins("W5"), IOStandard("LVCMOS15")),

    # DDR3, 32-bit bus across FPGA banks 34/35 (manual pp. 12-15).
    ("ddram", 0,
        Subsignal("a", Pins("AA4 AB2 AA5 AB5 AB1 U3 W1 T1 V2 U2 Y1 W2 Y2 U1 V3"), IOStandard("SSTL15")),
        Subsignal("ba", Pins("AA3 Y3 Y4"), IOStandard("SSTL15")),
        Subsignal("ras_n", Pins("V4"), IOStandard("SSTL15")),
        Subsignal("cas_n", Pins("W4"), IOStandard("SSTL15")),
        Subsignal("we_n", Pins("AA1"), IOStandard("SSTL15")),
        Subsignal("dm", Pins("D2 G2 M2 M5"), IOStandard("SSTL15")),
        Subsignal("dq", Pins(
            "C2 G1 A1 F3 B2 F1 B1 E2",
            "H3 G3 H2 H5 J1 J5 K1 H4",
            "L4 M3 L3 J6 K3 K6 J4 L5",
            "P1 N4 R1 N2 M6 N5 P6 P2"
        ), IOStandard("SSTL15"), Misc("IN_TERM=UNTUNED_SPLIT_50")),
        Subsignal("dqs_p", Pins("E1 K2 M1 P5"), IOStandard("DIFF_SSTL15"), Misc("IN_TERM=UNTUNED_SPLIT_50")),
        Subsignal("dqs_n", Pins("D1 J2 L1 P4"), IOStandard("DIFF_SSTL15"), Misc("IN_TERM=UNTUNED_SPLIT_50")),
        Subsignal("clk_p", Pins("R3"), IOStandard("DIFF_SSTL15")),
        Subsignal("clk_n", Pins("R2"), IOStandard("DIFF_SSTL15")),
        Subsignal("cke", Pins("T5"), IOStandard("SSTL15")),
        Subsignal("odt", Pins("U5"), IOStandard("SSTL15")),
        Subsignal("reset_n", Pins("W6"), IOStandard("LVCMOS15")),
        Subsignal("cs_n", Pins("AB3"), IOStandard("SSTL15")),
        Misc("SLEW=FAST"),
    ),

    # 128-Mbit QSPI flash (manual p. 16).
    # FPGA configuration clock is the dedicated CCLK pin; only user-accessible
    # flash signals are listed here.
    ("flash_cs_n", 0, Pins("T19"), IOStandard("LVCMOS33")),
    ("flash", 0,
        Subsignal("mosi", Pins("P22")),
        Subsignal("miso", Pins("R22")),
        Subsignal("wp", Pins("P21")),
        Subsignal("hold", Pins("R21")),
        IOStandard("LVCMOS33"),
    ),
]

# Carrier-board 40-pin headers J11 and J13 (manual pp. 43-45).
# These are raw FPGA pins, grouped in header pin order excluding power/GND.
_connectors = [
    ("j11",
        "G21 G22 C22 B22 F19 F20 D20 C20 A18 A19 B20 A20 "
        "F18 E18 E19 D19 C18 C19 B17 B18 D17 C17 A15 A16 "
        "B15 B16 A13 A14 E16 D16 C14 C15 F16 E17"
    ),
    ("j13",
        "W16 W15 T15 T14 V15 U15 V14 V13 W12 W11 Y12 Y11 "
        "W10 V10 AA10 AA11 AA9 AB10 U16 T16 AA13 AB13 AB11 "
        "AB12 Y13 AA14 W14 Y14 Y16 AA16 AB16 AB17 AA15 AB15"
    ),
]


class Platform(Xilinx7SeriesPlatform):
    default_clk_name = "clk200"
    default_clk_period = 1e9 / 200e6

    def __init__(self):
        Xilinx7SeriesPlatform.__init__(
            self,
            "xc7a200t-fbg484-2",
            _io,
            _connectors,
            toolchain="vivado",
        )

        # DDR3 bank reference voltage, per the core-board design.
        self.add_platform_command(
            "set_property INTERNAL_VREF 0.750 [get_iobanks 34]"
        )
        self.add_platform_command(
            "set_property INTERNAL_VREF 0.750 [get_iobanks 35]"
        )

        self.toolchain.bitstream_commands = [
            "set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]",
            "set_property BITSTREAM.CONFIG.CONFIGRATE 16 [current_design]",
            "set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]",
            "set_property CFGBVS VCCO [current_design]",
            "set_property CONFIG_VOLTAGE 3.3 [current_design]",
        ]

        self.toolchain.additional_commands = [
            'write_cfgmem -force -format bin -interface spix4 -size 16 '
            '-loadbit "up 0x0 {build_name}.bit" -file {build_name}.bin'
        ]

    def detect_ftdi_chip(self):
        """Detect common FTDI JTAG cables for OpenFPGALoader."""
        result = subprocess.run(
            ["lsusb"], capture_output=True, text=True, check=False
        )
        output = result.stdout.lower()
        for chip in ("ft232", "ft2232", "ft4232"):
            if chip in output:
                return chip
        return None

    def create_programmer(self, name="openfpgaloader"):
        cable = self.detect_ftdi_chip()
        return OpenFPGALoader(
            cable=cable,
            fpga_part="xc7a200tfbg484",
            freq=10e6,
        )

    def do_finalize(self, fragment):
        Xilinx7SeriesPlatform.do_finalize(self, fragment)
        self.add_period_constraint(
            self.lookup_request("clk200", loose=True), 1e9 / 200e6
        )
