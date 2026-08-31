use std::env;

fn main() {
    println!("==========================================");
    println!("      ZEROSPACE RUST SANDBOX TEST UTILITY ");
    println!("==========================================");
    
    // Demonstrate using a dependency
    let test_bytes = b"ZeroSpace";
    let encoded = hex::encode(test_bytes);
    println!("Hex library check: 'ZeroSpace' -> {}", encoded);
    
    let userprofile = env::var("USERPROFILE").unwrap_or_else(|_| "NOT SET".to_string());
    let temp = env::var("TEMP").unwrap_or_else(|_| "NOT SET".to_string());
    let path = env::var("PATH").unwrap_or_else(|_| "NOT SET".to_string());
    
    println!("USERPROFILE: {}", userprofile);
    println!("TEMP: {}", temp);
    println!("PATH: {}", path);
    
    if userprofile.contains("containers") {
        println!("\n[SUCCESS] Environment folders isolated inside ZeroSpace containers!");
    } else {
        println!("\n[WARNING] USERPROFILE does not contain 'containers'.");
    }
}
