MEMORY { FLASH : ORIGIN = 0x08000000, LENGTH = 64K  RAM : ORIGIN = 0x20000000, LENGTH = 20K }
ENTRY(reset);
SECTIONS {
  .vectors ORIGIN(FLASH) : { LONG(ORIGIN(RAM) + LENGTH(RAM)); LONG(reset | 1); KEEP(*(.vectors)); } > FLASH
  .text : { *(.text .text.*) } > FLASH
  .rodata : { *(.rodata .rodata.*) } > FLASH
  /DISCARD/ : { *(.ARM.exidx .ARM.exidx.*) }
}
