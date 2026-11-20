fn main(){ println!("cargo:rustc-link-search={}", std::env::var("CARGO_MANIFEST_DIR").unwrap()); println!("cargo:rerun-if-changed=link.x"); }
