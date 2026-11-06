// Observation-only module inside upstream image.rs. Decisions execute C bootutil.
use super::*;
use ring::digest::{digest, SHA256};

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|value| format!("{value:02x}")).collect()
}

fn observe(images: &Images, flash: &SimMultiFlash, id: &str, point: &str,
           boot_ok: bool, interrupted: bool) {
    let mut slots = Vec::new();
    for slot in &images.images[0].slots {
        let dev = flash.get(&slot.dev_id).unwrap();
        let mut data = vec![0; slot.len];
        dev.read(slot.base_off, &mut data).unwrap();
        let align = c::boot_max_align();
        let mut trailer = vec![0; c::boot_magic_sz() + align * 3];
        dev.read(slot.trailer_off + align, &mut trailer).unwrap();
        let revision = u16::from_le_bytes([data[22], data[23]]);
        let build = u32::from_le_bytes(data[24..28].try_into().unwrap());
        slots.push(format!("{{\"address\":{},\"version\":\"{}.{}.{}.{}\",\"header\":\"{}\",\"sha256\":\"{}\",\"trailer\":\"{}\",\"image_ok_raw\":{},\"copy_done_raw\":{}}}",
            slot.base_off, data[20], data[21], revision, build, hex(&data[..32]),
            hex(digest(&SHA256, &data).as_ref()), hex(&trailer), trailer[align*2], trailer[align]));
    }
    eprintln!("DIFF_JSON {{\"scenario\":\"{id}\",\"checkpoint\":\"{point}\",\"boot_ok\":{boot_ok},\"interrupted\":{interrupted},\"original_present_primary\":{},\"candidate_present_primary\":{},\"slots\":[{}]}}",
        images.verify_images(flash, 0, 0), images.verify_images(flash, 0, 1), slots.join(","));
}

fn boot(images: &Images, flash: &mut SimMultiFlash, id: &str, point: &str, cut: Option<i32>) {
    let mut counter = cut.unwrap_or(0);
    let result = c::boot_go(flash, &images.areadesc,
        if cut.is_some() { Some(&mut counter) } else { None }, None, false);
    eprintln!("NATIVE_BOOT scenario={id} checkpoint={point} cut={cut:?} result={result:?}");
    observe(images, flash, id, point, result.success_no_asserts(), result.interrupted());
    if cut.is_some() { assert!(result.interrupted(), "requested cut did not execute"); }
}

#[test]
fn differential_reference_scenarios() {
    assert!(Caps::SwapUsingScratch.present() && Caps::RSA2048.present()
        && Caps::ValidatePrimarySlot.present());
    assert_eq!(Caps::get_num_images(), 1);
    for id in ["test_upgrade", "confirmed_reboot", "unconfirmed_revert",
               "unauthorized_revert", "invalid_signature", "payload_corruption",
               "swap_power_loss", "interrupted_revert", "failed_trial",
               "repeated_resets", "known_good_recovery", "post_confirm_campaign_recovery"] {
        let builder = ImagesBuilder::new(DeviceName::K64f, 8, 0xff).unwrap();
        let images = if id == "invalid_signature" {
            builder.make_bad_secondary_slot_image(ImageManipulation::BadSignature)
        } else { builder.make_image(&NO_DEPS, false) };
        let mut flash = images.flash.clone();
        if id == "invalid_signature" { images.mark_upgrades(&mut flash, 1); }
        observe(&images, &flash, id, "initial", false, false);
        if id == "payload_corruption" || id == "known_good_recovery" {
            let slot = &images.images[0].slots[1];
            let dev = flash.get_mut(&slot.dev_id).unwrap();
            let mut data = [0u8; 8];
            let offset = slot.base_off + 32;
            dev.read(offset, &mut data).unwrap();
            let byte = data.iter_mut().find(|value| **value != 0).unwrap();
            *byte &= *byte - 1;
            // External stored-byte corruption, not a legal second programming command.
            // Restore the flash model's normal write checks before invoking bootutil.
            dev.set_verify_writes(false);
            dev.write(offset, &data).unwrap();
            dev.set_verify_writes(true);
            observe(&images, &flash, id, "corrupted", false, false);
        }
        if id == "swap_power_loss" {
            boot(&images, &mut flash, id, "cut", Some(7));
        }
        boot(&images, &mut flash, id, "first_boot", None);
        if id == "confirmed_reboot" || id == "post_confirm_campaign_recovery" {
            images.mark_permanent_upgrades(&mut flash, 0);
            observe(&images, &flash, id, "confirmation_write", false, false);
        }
        if id == "interrupted_revert" {
            boot(&images, &mut flash, id, "cut", Some(7));
        }
        if !["test_upgrade", "invalid_signature", "payload_corruption", "known_good_recovery", "swap_power_loss"].contains(&id) {
            boot(&images, &mut flash, id, "reset_1", None);
        }
        if id == "repeated_resets" {
            boot(&images, &mut flash, id, "reset_2", None);
            boot(&images, &mut flash, id, "reset_3", None);
        }
    }
}
