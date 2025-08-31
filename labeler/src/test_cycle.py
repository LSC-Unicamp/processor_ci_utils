import cocotb
import os
import json
import logging
from cocotb.triggers import RisingEdge, Timer
from cocotb.clock import Clock

# RISC-V encodings
NOP = 0x00000013          # addi x0, x0, 0
INSTR_A = 0x00500093      # addi x1, x0, 5  (example "random" instruction)
INSTR_B = 0x00600093      # addi x1, x0, 6  (example second instruction)
ADDI_X1_X0_5 = INSTR_A

def encode_jal(imm, rd=0):
    """
    Correctly encode RISC-V JAL for signed imm (bytes).
    imm: signed integer offset = target_pc - current_pc (in bytes).
    rd: destination register (0 to discard link).
    Returns 32-bit instruction word.
    """
    # J-format immediate is 21 bits with sign (imm[20:1] plus sign bit)
    # Valid range: -(1<<20) .. (1<<20)-1
    if not (-(1 << 20) <= imm < (1 << 20)):
        raise ValueError(f"JAL immediate {imm} out of range for 21-bit signed J-format")

    # Convert signed imm to unsigned 21-bit two's complement representation
    imm_u = imm & ((1 << 21) - 1)   # imm_u is 21-bit unsigned

    # Extract fields per RISC-V J format
    imm20   = (imm_u >> 20) & 0x1
    imm10_1 = (imm_u >> 1)  & 0x3FF
    imm11   = (imm_u >> 11) & 0x1
    imm19_12= (imm_u >> 12) & 0xFF

    opcode = 0x6f
    instr = (imm20 << 31) | (imm10_1 << 21) | (imm11 << 20) | (imm19_12 << 12) | ((rd & 0x1F) << 7) | opcode
    return instr & 0xFFFFFFFF

async def instr_mem_driver(dut, required_loops=1, jump_check_cycles=12):
    dut.core_data_in.value = 0
    dut.core_ack.value = 0

    start_addr = None
    loop_start = None
    branch_addr = None
    finish_addr = None
    jal_back = None

    pending = False
    pending_addr = None
    pending_instr = None

    loops_done = 0

    while True:
        await RisingEdge(dut.sys_clk)

        # handle delivery of pending read
        if pending:
            dut.core_data_in.value = pending_instr
            dut.core_ack.value = 1
            dut._log.info(f"[WB] ACK A=0x{pending_addr:08x} D=0x{pending_instr:08x}")
            addr_this = pending_addr
            instr_this = pending_instr
            pending = False

            # === Detect JAL-back delivery ===
            if addr_this == branch_addr and instr_this == jal_back:
                dut._log.info("[driver] Delivered JAL_back. Watching PC requests...")

                observed = False
                for i in range(jump_check_cycles):
                    await RisingEdge(dut.sys_clk)
                    if dut.core_cyc.value and dut.core_stb.value and not dut.core_we.value:
                        if dut.core_addr.value.is_resolvable:
                            pc_now = dut.core_addr.value.integer
                            dut._log.info(f"[driver-check] after JAL step {i}: core_addr={pc_now:08x}")
                            if pc_now == loop_start:
                                loops_done += 1
                                dut._log.info(f"[driver] Observed jump back to loop_start (loop {loops_done})")
                                observed = True
                                break
                if not observed:
                    dut._log.warning("[driver] JAL did not cause jump to loop_start within check window")

            continue  # wait for next request

        # default: deassert ack unless serving
        dut.core_ack.value = 0

        # see if there’s a new fetch request
        if not (dut.core_cyc.value and dut.core_stb.value and not dut.core_we.value):
            continue
        if not dut.core_addr.value.is_resolvable:
            continue

        addr = dut.core_addr.value.integer

        # initialize loop layout on first request
        if start_addr is None:
            start_addr = addr
            loop_start = start_addr + 8
            branch_addr = start_addr + 32
            finish_addr = start_addr + 36
            imm = loop_start - branch_addr
            try:
                jal_back = encode_jal(imm, rd=0)
            except ValueError as e:
                dut._log.error(f"encode_jal error: {e}, imm={imm}")
                jal_back = NOP
            dut._log.info(
                f"[driver] start=0x{start_addr:08x}, loop_start=0x{loop_start:08x}, "
                f"branch=0x{branch_addr:08x}, finish=0x{finish_addr:08x}, jal=0x{jal_back:08x}"
            )

        # instruction map
        if addr == start_addr + 0:
            next_instr = INSTR_A
        elif addr == start_addr + 4:
            next_instr = INSTR_B
        elif addr in (start_addr+8, start_addr+12, start_addr+16,
                      start_addr+20, start_addr+24, start_addr+28):
            next_instr = NOP
        elif addr == branch_addr:
            if loops_done < required_loops:
                next_instr = jal_back
            else:
                next_instr = NOP  # stop looping
        elif addr == finish_addr:
            next_instr = NOP
        else:
            next_instr = NOP

        # queue to return next cycle
        pending = True
        pending_addr = addr
        pending_instr = next_instr




async def measure_pipeline_depth(dut, regfile):
    """
    Measure fetch->WB latency for the ADDI at start_addr (we detect ADDI by matching core_data_in).
    Returns latency (int) or None on failure.
    """
    x1_idx = 1

    # sample baseline for reg x1 after aligning to clock
    await RisingEdge(dut.sys_clk)
    try:
        baseline = int(regfile[x1_idx].value) if regfile[x1_idx].value.is_resolvable else 0
    except Exception:
        baseline = 0

    issue_cycle = None
    write_cycle = None
    max_cycles = 400

    for cycle in range(max_cycles):
        await RisingEdge(dut.sys_clk)

        # read what we are returning on the instruction bus (what core is fetching)
        fetched = None
        try:
            if dut.core_data_in.value.is_resolvable:
                fetched = int(dut.core_data_in.value)
        except Exception:
            fetched = None

        pc_val = dut.core_addr.value.integer if dut.core_addr.value.is_resolvable else None
        dut._log.info(f"[measure] cycle={cycle}, pc={pc_val}, fetched={fetched:#010x}" if fetched is not None else f"[measure] cycle={cycle}, pc={pc_val}, fetched=None")

        # detect ADDI fetch by matching the value we return
        if issue_cycle is None and fetched == ADDI_X1_X0_5 and dut.core_stb.value:
            issue_cycle = cycle
            dut._log.info(f"[measure] Observed ADDI fetch at cycle {cycle} (pc={pc_val:#010x})")

        # once fetch observed, wait for regfile[x1] to change
        if issue_cycle is not None:
            try:
                if regfile[x1_idx].value.is_resolvable:
                    new_val = int(regfile[x1_idx].value)
                    if new_val != baseline:
                        write_cycle = cycle
                        dut._log.info(f"[measure] regfile x1 changed to {new_val} at cycle {cycle}")
                        break
            except Exception:
                # unresolved this cycle; continue
                pass

    if issue_cycle is None or write_cycle is None:
        dut._log.warning(f"[measure] failed to observe fetch/write (issue={issue_cycle}, write={write_cycle})")
        return None

    # +1 convention (include write cycle as visible)
    latency = write_cycle - issue_cycle + 1
    dut._log.info(f"[measure] measured latency (fetch → WB) = {latency} cycles (issue={issue_cycle}, write={write_cycle})")
    return latency


async def test_pc_behavior(dut, regfile):
    """
    Main test:
      - warmup loop with real JAL back to loop_start for required_loops iterations (>=15)
      - after warmup, run test program and classify core
      - save results to JSON file in OUTPUT_DIR
    """
    dut._log.info(f"Starting PC behavior test for {dut._name}")
    dut._log.info(f"Using register file handle: {regfile}")

    # init driven signals
    dut.core_ack.value = 0
    dut.core_data_in.value = 0

    cocotb.start_soon(Clock(dut.sys_clk, 10, units="ns").start())

    # pick required loops from env or default 15
    required_loops = 25

    cocotb.start_soon(instr_mem_driver(dut, required_loops=required_loops))

    # Reset sequence (active-low rst_n)
    dut.rst_n.value = 0
    dut.core_ack.value = 0
    await Timer(50, units="ns")
    dut.rst_n.value = 1

    # Observe PC for a while post-warmup/test switch
    prev_pc = None
    change_cycles = []
    last_change = None
    first_pc_seen = None

    # larger observation window to allow warmup to finish and test mapping to run
    for cycle in range(200):
        await RisingEdge(dut.sys_clk)
        if not dut.core_addr.value.is_resolvable:
            continue
        pc = dut.core_addr.value.integer
        dut._log.info(f"[observe] cycle={cycle}: PC=0x{pc:08x}")

        if first_pc_seen is None:
            first_pc_seen = pc
            prev_pc = pc
            last_change = cycle
            continue

        if pc != prev_pc:
            change_cycles.append(cycle - last_change)
            last_change = cycle
            prev_pc = pc

    filtered = [d for d in change_cycles if d > 0]

    # prepare JSON output
    output_dir = os.environ.get('OUTPUT_DIR', "output")
    os.makedirs(output_dir, exist_ok=True)
    processor_name = os.path.basename(output_dir) or "processor"
    output_file = os.path.join(output_dir, f"{processor_name}_labels.json")

    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
    except Exception:
        existing_data = {}

    if filtered and all(d == 1 for d in filtered):
        dut._log.info("Likely pipelined core (PC changes every cycle after warmup).")
        latency = await measure_pipeline_depth(dut, regfile)
        if latency is None:
            dut._log.warning("Could not measure pipeline depth.")
            existing_data[processor_name] = {"multicycle": False, "pipeline": False, "singlecycle": False}
        elif latency == 1:
            dut._log.info("Detected SINGLE-CYCLE core (fetch→WB in 1 cycle).")
            existing_data[processor_name] = {"multicycle": False, "pipeline": False, "singlecycle": True}
        elif latency > 1:
            dut._log.info(f"Detected PIPELINED core with depth ≈ {latency} (fetch→WB).")
            existing_data[processor_name] = {"multicycle": False, "pipeline": {"depth": latency}, "singlecycle": False}
        else:
            dut._log.warning(f"Unexpected latency value: {latency}")
            existing_data[processor_name] = {"multicycle": False, "pipeline": False, "singlecycle": False}
    else:
        dut._log.info("Likely multicycle core (PC stalls between changes).")
        existing_data[processor_name] = {"multicycle": True, "pipeline": False, "singlecycle": False}

    # write results
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=4)
        dut._log.info(f"Results saved to {output_file}")
    except OSError as e:
        dut._log.warning("Error writing to JSON file: %s", e)
