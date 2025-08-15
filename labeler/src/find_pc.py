import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

NOP = 0x00000013

def find_32bit_signals(handle):
    """Recursively find all 32-bit signals in the DUT."""
    candidates = []
    for _, obj in handle._sub_handles.items():
        if hasattr(obj, "value"):
            try:
                if len(obj) == 32:
                    candidates.append(obj)
            except Exception:
                pass
        candidates.extend(find_32bit_signals(obj))
    return candidates

async def instr_mem_driver(dut, jump_after=3, jump_offset=0x40):
    """Simple IMEM driver that jumps fetch address after a few cycles."""
    start_addr = None
    cycles = 0
    while True:
        await RisingEdge(dut.sys_clk)
        if dut.core_cyc.value and dut.core_stb.value and not dut.core_we.value:
            addr = dut.core_addr.value.integer
            if start_addr is None:
                start_addr = addr
            if cycles < jump_after:
                dut.core_data_in.value = NOP
            else:
                dut.core_data_in.value = NOP
                addr = start_addr + jump_offset
            dut.core_ack.value = 1
            cycles += 1
        else:
            dut.core_ack.value = 0

@cocotb.test()
async def hunt_pc_active(dut):
    cocotb.start_soon(Clock(dut.sys_clk, 10, units="ns").start())
    cocotb.start_soon(instr_mem_driver(dut))

    # Reset core
    dut.rst_n.value = 0
    dut.core_ack.value = 0
    await Timer(50, units="ns")
    dut.rst_n.value = 1

    # Find all 32-bit signals
    signals = find_32bit_signals(dut)
    dut._log.info(f"Found {len(signals)} possible 32-bit signals")

    history = {sig: [] for sig in signals}

    # Record for ~10 cycles
    for _ in range(10):
        await RisingEdge(dut.sys_clk)
        for sig in signals:
            history[sig].append(sig.value.integer)

    # Detect pattern: +4 increments then a big jump
    possible_pc = []
    for sig, values in history.items():
        if len(values) < 4:
            continue
        deltas = [values[i+1] - values[i] for i in range(len(values)-1)]
        if all(d == 4 for d in deltas[:3]) and any(abs(d) >= 0x40 for d in deltas[3:]):
            possible_pc.append(sig)

    if possible_pc:
        dut._log.info("Likely PC signals:")
        for sig in possible_pc:
            dut._log.info(f"  {sig._name}: {history[sig]}")
    else:
        dut._log.warning("No PC-like signal detected.")
