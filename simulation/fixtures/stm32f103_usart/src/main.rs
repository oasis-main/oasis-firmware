#![no_std]
#![no_main]
use core::ptr::{read_volatile, write_volatile};
const RCC_APB2ENR: *mut u32 = 0x4002_1018 as *mut u32;
const USART1_SR: *const u32 = 0x4001_3800 as *const u32;
const USART1_DR: *mut u32 = 0x4001_3804 as *mut u32;
const USART1_CR1: *mut u32 = 0x4001_380C as *mut u32;
fn put(b: u8) { unsafe { while read_volatile(USART1_SR) & (1 << 7) == 0 {} write_volatile(USART1_DR, b as u32); } }
#[no_mangle]
pub extern "C" fn reset() -> ! {
    unsafe {
        write_volatile(RCC_APB2ENR, read_volatile(RCC_APB2ENR) | (1 << 14) | (1 << 2));
        write_volatile(USART1_CR1, (1 << 13) | (1 << 3));
    }
    for b in b"oasis f103 hello\r\n" { put(*b); }
    loop {}
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! { loop {} }
