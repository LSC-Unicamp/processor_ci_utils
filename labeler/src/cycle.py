import cocotb
from cocotb.triggers import RisingEdge, Timer



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
    
