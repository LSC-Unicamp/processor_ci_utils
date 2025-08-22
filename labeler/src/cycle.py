import cocotb
from cocotb.triggers import RisingEdge, Timer
from cocotb.clock import Clock


# Example program: addi x1, x0, 5 followed by NOPs
prog = {
    0x00000080: 0x00500093,  # addi x1, x0, 5
    0x00000084: 0x00000013,  # NOP
    0x00000088: 0x00000013,  # NOP
}


async def instr_mem_driver(dut):
    dut.core_data_in.value = 0
    dut.core_ack.value = 0
    while True:
        await RisingEdge(dut.sys_clk)
        if dut.core_cyc.value and dut.core_stb.value and not dut.core_we.value:
            addr_val = dut.core_addr.value
            if addr_val.is_resolvable:
                addr = addr_val.integer
            else:
                continue
            instr = prog.get(addr, 0x00000013)  # default NOP
            dut.core_data_in.value = instr
            dut.core_ack.value = 1
        else:
            dut.core_ack.value = 0


async def measure_pipeline_depth(dut, regfile):
    """Issue ADDI x1, x0, 5 and measure how many cycles until regfile[x1] is updated."""
    x1_idx = 1

    # Record initial value of x1, handle 'x' states
    await RisingEdge(dut.sys_clk)
    try:
        if regfile[x1_idx].value.is_resolvable:
            baseline = int(regfile[x1_idx].value)
        else:
            baseline = 0  # Default to 0 if unresolvable ('x' state)
    except (ValueError, AttributeError):
        baseline = 0  # Default to 0 if conversion fails

    issue_cycle = None
    write_cycle = None

    for cycle in range(50):
        await RisingEdge(dut.sys_clk)
        
        pc = dut.core_addr.value.integer if dut.core_addr.value.is_resolvable else None
        dut._log.info(f"Cycle {cycle}: PC = {pc:#010x}")

        # When ADDI is fetched (at PC = 0x00000080)
        if issue_cycle is None and dut.core_addr.value.is_resolvable:
            if dut.core_addr.value.integer == 0x00000080:
                issue_cycle = cycle
                dut._log.info(f"Instruction issued at cycle {cycle}: ADDI x1, x0, 5")

        # Detect when x1 changes
        if issue_cycle is not None:
            try:
                if regfile[x1_idx].value.is_resolvable:
                    new_val = int(regfile[x1_idx].value)
                    if new_val != baseline and new_val != 0:  # Ignore transitions from 'x' to 0
                        write_cycle = cycle
                        dut._log.info(f"x1 updated to {new_val} at cycle {cycle}")
                        break
            except (ValueError, AttributeError):
                continue  # Skip this cycle if value is still unresolvable

    if issue_cycle is not None and write_cycle is not None:
        latency = write_cycle - issue_cycle + 1  # +1 to include the write cycle
        dut._log.info(f"Pipeline depth (latency to WB) = {latency} cycles")
    else:
        dut._log.warning("Could not measure pipeline depth (no regfile change detected).")


@cocotb.test()
async def test_pc_behavior(dut, regfile):
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
    first_pc_seen = None

    # Observe PC for 30 cycles
    for cycle in range(30):
        await RisingEdge(dut.sys_clk)
        if not dut.core_addr.value.is_resolvable:
            continue
        pc = dut.core_addr.value.integer
        dut._log.info(f"Cycle {cycle}: PC = {pc:#010x}")

        # Skip "stall" period where PC stays constant at reset vector
        if first_pc_seen is None:
            first_pc_seen = pc
            continue
        if prev_pc is None:
            prev_pc = pc
            last_change = cycle
            continue

        if pc != prev_pc:
            change_cycles.append(cycle - last_change)
            last_change = cycle
        prev_pc = pc

    # Ignore initial reset stalls (all 0s or repeated same PC)
    filtered = [d for d in change_cycles if d > 0]

    if filtered and all(delta == 1 for delta in filtered):
        dut._log.info("Likely pipelined core (PC changes every cycle after reset).")
        await measure_pipeline_depth(dut, regfile)
    else:
        dut._log.info("Likely multicycle core (PC stalls between changes).")
