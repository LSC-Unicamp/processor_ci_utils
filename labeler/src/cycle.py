import cocotb
import os
import json
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
    """
    Issue ADDI x1, x0, 5 and measure how many cycles until regfile[x1] is updated.
    Returns measured latency (int) or None on failure.
    """
    x1_idx = 1

    # Align to clock and sample a baseline for x1 (handle 'x' safely)
    await RisingEdge(dut.sys_clk)
    try:
        baseline = int(regfile[x1_idx].value) if regfile[x1_idx].value.is_resolvable else 0
    except Exception:
        baseline = 0

    issue_cycle = None
    write_cycle = None

    # Maximum observation window
    max_cycles = 200

    for cycle in range(max_cycles):
        await RisingEdge(dut.sys_clk)

        # Safe PC read
        if dut.core_addr.value.is_resolvable:
            pc_val = dut.core_addr.value.integer
        else:
            pc_val = None

        dut._log.debug(f"[measure] cycle={cycle} pc={pc_val}")

        # Detect when ADDI is fetched (at PC=0x00000080)
        if issue_cycle is None and pc_val == 0x00000080 and dut.core_stb.value:
            issue_cycle = cycle
            dut._log.info(f"[measure] ADDI fetch observed at cycle {cycle} (PC=0x00000080)")

        # If register bank exposes write port signals, prefer them (more precise).
        # Best-effort search — names vary between cores, so we check common ones.
        # If you have explicit we/waddr signals, replace this with direct handles.
        # Fallback: detect by regfile value change.
        if issue_cycle is not None:
            # fallback detection by observing regfile value change
            try:
                if regfile[x1_idx].value.is_resolvable:
                    new_val = int(regfile[x1_idx].value)
                    if new_val != baseline:
                        write_cycle = cycle
                        dut._log.info(f"[measure] regfile x1 changed to {new_val} at cycle {cycle}")
                        break
            except Exception:
                # unresolved this cycle; keep waiting
                pass

    if issue_cycle is None or write_cycle is None:
        dut._log.warning(f"[measure] failed to observe fetch/write (issue={issue_cycle}, write={write_cycle})")
        return None

    # Keep your +1 convention to include the write cycle as visible
    latency = write_cycle - issue_cycle + 1
    dut._log.info(f"[measure] measured latency (fetch → WB) = {latency} cycles (issue={issue_cycle}, write={write_cycle})")
    return latency


@cocotb.test()
async def test_pc_behavior(dut, regfile):
    # initialize driven signals
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
    last_change = None
    first_pc_seen = None

    # Observe PC for 30 cycles (post-reset). Samples after rising edge.
    for cycle in range(30):
        await RisingEdge(dut.sys_clk)
        if not dut.core_addr.value.is_resolvable:
            continue
        pc = dut.core_addr.value.integer
        dut._log.info(f"Cycle {cycle}: PC = {pc:#010x}")

        # Skip initial stall period (keep first seen PC as baseline)
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

    output_dir = os.environ.get('OUTPUT_DIR', "default")
    processor_name = os.path.basename(output_dir)
    output_file = os.path.join(output_dir, f"{processor_name}_labels.json")
    if not os.path.exists(output_file):
        with open(output_file, 'w', encoding='utf-8') as json_file:
            json.dump({}, json_file, indent=4)
    try:
        with open(output_file, 'r', encoding='utf-8') as json_file:
            existing_data = json.load(json_file)
    except (json.JSONDecodeError, OSError) as e:
        logging.warning('Error reading existing JSON file: %s', e)
        existing_data = {}

    # Filter out zero-length intervals (shouldn't happen, but safe)
    filtered = [d for d in change_cycles if d > 0]

    if filtered and all(delta == 1 for delta in filtered):
        dut._log.info("Likely pipelined core (PC changes every cycle after reset).")
        # measure pipeline depth (returns latency or None)
        latency = await measure_pipeline_depth(dut, regfile)

        if latency is None:
            dut._log.warning("Could not measure pipeline depth.")
        elif latency == 1:
            dut._log.info("Detected SINGLE-CYCLE core (fetch→WB in 1 cycle).")
            existing_data[processor_name]["multicycle"] = False
            existing_data[processor_name]["pipeline"] = False
        elif latency > 1:
            dut._log.info(f"Detected PIPELINED core with depth ≈ {latency} (fetch→WB).")
            existing_data[processor_name]["multicycle"] = False
            existing_data[processor_name]["pipeline"] = {"depth": latency}
        else:
            dut._log.warning(f"Unexpected latency value: {latency}")
    else:
        dut._log.info("Likely multicycle core (PC stalls between changes).")
        existing_data[processor_name]["multicycle"] = True
        existing_data[processor_name]["pipeline"] = False

    try:
        with open(output_file, 'w', encoding='utf-8') as json_file:
            json.dump(existing_data, json_file, indent=4)
        dut._log.info(f'Results saved to {output_file}')
    except OSError as e:
        logging.warning('Error writing to JSON file: %s', e)
