// Test-only observations around upstream simulator APIs; no boot decisions here.
// Compiled as a child module of upstream sim/src/image.rs.
use super::*;
use ring::digest::{digest, SHA256};

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn observe(images: &Images, flash: &SimMultiFlash, checkpoint: &str) {
    for (index, image) in images.images.iter().enumerate() {
        for (slot_index, slot) in image.slots.iter().enumerate() {
            let dev = flash.get(&slot.dev_id).unwrap();
            let mut bytes = vec![0; slot.len];
            dev.read(slot.base_off, &mut bytes).unwrap();
            let mut trailer = vec![0; c::boot_magic_sz() + c::boot_max_align() * 3];
            dev.read(slot.trailer_off + c::boot_max_align(), &mut trailer).unwrap();
            let align = c::boot_max_align();
            eprintln!("OBS checkpoint={checkpoint} image={index} slot={slot_index} address={:#x} length={} sha256={} header={} trailer={} image_ok_raw={:#x} copy_done_raw={:#x}",
                slot.base_off, slot.len, hex(digest(&SHA256, &bytes).as_ref()),
                hex(&bytes[..32]), hex(&trailer), trailer[align * 2], trailer[align]);
        }
    }
    eprintln!("OBS checkpoint={checkpoint} primary_is_original={} primary_is_candidate={}",
        images.verify_images(flash, 0, 0), images.verify_images(flash, 0, 1));
}

fn fixture() -> Images {
    assert!(Caps::SwapUsingScratch.present());
    assert!(Caps::RSA2048.present());
    assert!(Caps::ValidatePrimarySlot.present());
    assert_eq!(Caps::get_num_images(), 1);
    assert!(!Caps::OverwriteUpgrade.present());
    eprintln!("CONFIG scratch=true rsa2048=true validate_primary=true images=1 device=k64f align=8 erased=ff");
    ImagesBuilder::new(DeviceName::K64f, 8, 0xff)
        .expect("selected upstream flash layout must be supported")
        .make_image(&NO_DEPS, false)
}

#[test]
fn reference_test_upgrade_confirm_persists() {
    let images = fixture();
    let mut flash = images.flash.clone();
    observe(&images, &flash, "confirm_initial");
    assert!(images.verify_images(&flash, 0, 0));
    let result = c::boot_go(&mut flash, &images.areadesc, None, None, false);
    eprintln!("BOOT checkpoint=confirm_test_upgrade result={result:?}");
    assert!(result.success_no_asserts());
    assert!(images.verify_images(&flash, 0, 1));
    assert!(images.verify_trailers(&flash, 0, BOOT_MAGIC_GOOD, BOOT_FLAG_UNSET, BOOT_FLAG_SET));
    observe(&images, &flash, "confirm_trial");
    // Same external application-confirmation stimulus used by upstream run_norevert.
    images.mark_permanent_upgrades(&mut flash, 0);
    observe(&images, &flash, "confirm_metadata_written");
    let result = c::boot_go(&mut flash, &images.areadesc, None, None, false);
    eprintln!("BOOT checkpoint=confirm_reboot result={result:?}");
    assert!(result.success_no_asserts());
    assert!(images.verify_images(&flash, 0, 1));
    assert!(images.verify_trailers(&flash, 0, BOOT_MAGIC_GOOD, BOOT_FLAG_SET, BOOT_FLAG_SET));
    observe(&images, &flash, "confirm_reboot");
}

#[test]
fn reference_unconfirmed_test_reverts() {
    let images = fixture();
    let mut flash = images.flash.clone();
    observe(&images, &flash, "revert_initial");
    let result = c::boot_go(&mut flash, &images.areadesc, None, None, false);
    eprintln!("BOOT checkpoint=revert_test_upgrade result={result:?}");
    assert!(result.success_no_asserts());
    assert!(images.verify_images(&flash, 0, 1));
    observe(&images, &flash, "revert_trial");
    // No confirmation. A new boot invocation uses retained flash, fresh C context.
    let result = c::boot_go(&mut flash, &images.areadesc, None, None, false);
    eprintln!("BOOT checkpoint=revert_reboot result={result:?}");
    assert!(result.success_no_asserts());
    assert!(images.verify_images(&flash, 0, 0));
    observe(&images, &flash, "revert_reboot");
}
