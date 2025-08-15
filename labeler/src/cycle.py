import cocotb
from cocotb.triggers import RisingEdge, Timer
from cocotb.clock import Clock


# Example program: addi x1, x0, 5 followed by NOPs
prog = {
    0x80000000: 0x00500093,  # addi x1, x0, 5
    0x80000004: 0x00000013,  # NOP
    0x80000008: 0x00000013,  # NOP
}

async def instr_mem_driver(dut):
    while True:
        await RisingEdge(dut.sys_clk)
        # Only respond when the CPU is requesting an instruction
        if dut.core_cyc.value and dut.core_stb.value and not dut.core_we.value:
            addr_val = dut.core_addr.value
            if addr_val.is_resolvable:
                addr = addr_val.integer
            else:
                continue  # skip this cycle until addr is known
            instr = prog.get(addr, 0x00000013)  # default NOP
            dut.core_data_in.value = instr
            dut.core_ack.value = 1
        else:
            dut.core_ack.value = 0
    
@cocotb.test()
async def test_pc_behavior(dut):
    dut.core_ack.value = 0
    dut.core_data_in.value = 0

    cocotb.start_soon(Clock(dut.sys_clk, 10, units="ns").start())
    cocotb.start_soon(instr_mem_driver(dut))

    # Reset
    dut.rst_n.value = 0
    dut.core_ack.value = 0
    await Timer(50, units="ns")
    dut.rst_n.value = 1

    prev_pc = None
    change_cycles = []
    last_change = 0

    for cycle in range(20):
        await RisingEdge(dut.sys_clk)
        pc = dut.core_addr.value.integer
        dut._log.info(f"Cycle {cycle}: PC = {pc:#010x}")

        if prev_pc is not None and pc != prev_pc:
            change_cycles.append(cycle - last_change)
            last_change = cycle
        elif prev_pc is None:
            last_change = cycle
        prev_pc = pc

    if all(delta == 1 for delta in change_cycles):
        dut._log.info("Likely pipelined core (PC changes every cycle).")
    else:
        dut._log.info("Likely multicycle core (PC stalls between changes).")
    
