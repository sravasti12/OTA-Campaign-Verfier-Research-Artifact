# Raspberry Pi testbed: build plan

This is experiment E7 in `PLAN.md`: running the campaigns on real hardware with real power cuts, then comparing against frozen model predictions. **I can't build or run it; you do.** Nothing here
has been tested yet. Items marked **Check** are facts I could not confirm from an official source, so verify them before buying or wiring.

## What this adds over the simulator

| Question | SIL | Testbed |
| --- | --- | --- |
| Does losing power corrupt the flash? | No: a killed process keeps everything already written | **Yes: this is the main reason to build it** |
| Do "atomic" boot switches survive a cut? | Assumed | Measured |
| Are boot failures and watchdogs real? | No | Yes |
| Is a Pi a real automotive ECU? | No | **Also no.** It shows protocol behaviour under real power loss, not automotive conformance |

## Hardware list

Quantities assume 4 ECU nodes (Q3 in `PLAN.md`). Three nodes are enough for the existing 3-ECU campaign, and the fourth is a spare or adds a graph with more structure. Buy from any reputable supplier. I have not listed prices because I could not verify them.

| Item | Qty | Notes |
| --- | --- | --- |
| Raspberry Pi 4 Model B, 2 GB or more | 4 | The ECU nodes. Use the same model and revision on all of them |
| Raspberry Pi 4 or 5 | 1 | The controller. **Never cut its power.** A laptop on the same network can also do this, but it then needs a USB relay or GPIO adapter |
| Official-quality 5.1 V 3 A USB-C supply | 5 | One per Pi. Do not share one supply across nodes |
| 4-channel opto-isolated relay board | 1 | **Check** that the inputs trigger from 3.3 V logic, and that contacts are rated above 3 A at 5 V DC |
| USB-C inline breakout pairs (plug and socket, with screw terminals) | 4 | **Check** that they pass power and CC lines. This lets you switch 5 V without cutting cables |
| A2-rated microSD cards from one batch, 32 GB | 8 | Two per node. Cuts will wear and may kill cards, and spares let you tell a dead card from a real finding |
| Gigabit Ethernet switch, 8 port, and short cables | 1 + 5 | Wired only, so Wi-Fi does not add noise |
| USB-to-UART adapters, 3.3 V logic | 4 | **Must be 3.3 V.** A 5 V adapter can damage the Pi. Used to capture boot logs that survive a network failure |
| Powered USB hub | 1 | For the UART adapters on the controller |
| Jumper wires, 18 AWG hookup wire, ferrules, fused inline holder | - | Use thick wire on the 5 V path, because thin wire drops voltage under load |
| USB power meter | 1 | To confirm the node still sees 5 V through the relay under load |
| Oscilloscope or logic analyser (optional) | 1 | To measure how long a cut really takes |

**Optional:** a MOSFET load switch in place of the relay gives sharper, repeatable cuts. Start with the relay, which is simpler and easy to see working.

## Wiring

Everything here is **5 V DC on the output side of the supply. Do not switch mains. Never open a mains supply.**

### Power path, per ECU node

Break only the **5 V (VBUS)** line, using the relay's normally-open contact, so a node with an unpowered relay is off. Leave ground and CC lines connected.

```text
USB-C supply --> [breakout socket] --VBUS--> relay COM   relay NO --> VBUS--> [breakout plug] --> Pi USB-C
                                   --GND ------------------------------ GND-->
                                   --CC1/CC2 -------------------------- CC -->
```

Do not power through the GPIO 5 V pins, as one retailer guide warns the header has no regulation or fuse protection. Going through USB-C keeps the Pi's input protection in the path.

### Relay control, from the controller

| Controller pin | Goes to | Note |
| --- | --- | --- |
| A 5 V pin (physical 2 or 4) | Relay board VCC | **Check** the board's coil current. If it is high, power the board from a separate 5 V supply |
| GND (physical 6) | Relay board GND | Common ground with the controller |
| GPIO 17 (physical 11) | IN1, node 1 | Any free GPIO works; record the mapping |
| GPIO 27 (physical 13) | IN2, node 2 | |
| GPIO 22 (physical 15) | IN3, node 3 | |
| GPIO 23 (physical 16) | IN4, node 4 | |

**Check** your board's logic. Many boards are active-low, so a low input closes the relay. Set up the pin before connecting a node, so a controller reboot cannot power-cycle nodes unexpectedly.

### Serial logs, per ECU node

Connect each UART adapter to its node's GPIO header and to the powered hub on the controller. **Check** these pin numbers against the official pinout before connecting.

| Node pin | Adapter pin |
| --- | --- |
| GPIO 14 TX (physical 8) | RX |
| GPIO 15 RX (physical 10) | TX |
| GND (physical 6) | GND |

Do not connect the adapter's power pin. It could keep parts of the Pi powered and spoil a power cut.

### Network

Connect all five machines to the switch on a private subnet with fixed addresses, and nothing else on it.

## Software

**Boot and A/B.** Each node needs a real A/B layout. Two options, in order:

1. **Start here: Pi `tryboot` with `autoboot.txt`.** The Pi firmware can try a new partition once and fall back to the default. The official `config.txt` docs describe combining `autoboot.txt` with tryboot for A/B OS upgrades. Port `sil/ecu_agent.py` so
   slots are partitions and boot switching uses this mechanism. **Note:** replacing `autoboot.txt` itself is reported by a community thread to be a possible single point of failure. That is one user's reading, and the testbed should measure it.
2. **Then, for independence: RAUC.** Using a third-party update client stops the testbed being written by the same author as the model. RAUC with `meta-rauc-community` has Raspberry Pi support, but is a Yocto build. The sources I found pair it with U-Boot.
   **I found no source that RAUC integrates with `tryboot`, so assume U-Boot unless you confirm otherwise.**

Enable the hardware watchdog, so a hung node resets by itself.

**Controller.** Port `sil/harness.py`, replacing process kills with relay control. The fault scripts and predictions stay the same.

## Cutting power mid-install

The aim is a cut at a known point in the write, repeatably, without the node being warned.

1. The ECU agent logs progress during a write, for example each chunk, over the network and UART.
2. The controller waits for the chosen trigger, such as "chunk 8 of 16 started".
3. The controller waits a random delay from a seeded generator, then opens the relay. Random delays stop cuts always landing at the same point in a write.
4. It holds power off for a set time (start with 5 s, so capacitors drain).
5. It closes the relay, waits for boot or a timeout, and records the result.
6. It reads the slots, boot state and logs, and judges S1 to S4 from what is on the node, as `observe()` does.

**Trigger points to cover:** during image write; during verification; during the boot switch; during the first boot of the new image; during rollback; and just after an ECU acts but before the coordinator records it, which the current model and SIL do not include.

**Caveats:**

- The trigger message reaches the controller after the event, so there is a delay between trigger and cut. Measure it with the oscilloscope or logs, and report it.
- Relays take milliseconds to open, and the Pi keeps running briefly on its capacitors. So the cut's real moment is not the command's moment.
- SD cards have their own caches and controllers. Lost or torn writes here reflect the card as well as the protocol. Report the card model, and consider repeating key cases on a second card model.
- Filesystem choice and mount options affect results. Fix and record them.

## Bring-up order

Do these in order. Do not move on until each step passes.

1. **Power, without Pis.** With a meter, confirm the relay opens and closes 5 V on command, and which logic level does what.
2. **One node.** Confirm it boots through the relay, and the meter stays near 5 V under load. Watch for the Pi's under-voltage warning.
3. **Serial.** See boot logs on the controller.
4. **A/B alone.** Switch slots, roll back, and confirm a failed trial falls back, with no campaign running.
5. **100 repeated cuts on an idle node.** Count failures to boot. This gives a baseline for how often a cut alone causes trouble.
6. **All nodes.** Run a nominal campaign.
7. **Faults.** Run the fault scripts, without power cuts first.
8. **Power cuts.** Add them last.

## Running the experiment

- Freeze and commit predictions before the first run, as for the SIL.
- Use fixed seeds for delays, and at least 30 repetitions per timing-sensitive script, as set out in `PLAN.md`.
- Reflash each node from a known image between runs, unless the test is about accumulated damage.
- Commit raw logs to `results/raw/e7_testbed/<run-id>/`, including failed runs. Nothing is discarded because it looks like a hardware glitch. Mark it, and explain it.
- Record board revisions, firmware version, OS image hash, card model, and room temperature if a run looks odd.
- Treat `UNSUPPORTED` as its own result: if the model has no concept for what happened, do not count it as a match or a miss.

## What the testbed can and cannot show

**Can show:** whether the protocol's safety properties survive real power loss on real flash, and where the model's atomic-step assumptions fail.

**Cannot show:** automotive-grade behaviour, CAN or AUTOSAR behaviour, behaviour on real ECU flash and bootloaders, temperature or voltage extremes, or anything about certification.

## Sources

- [Raspberry Pi config.txt documentation](https://raspberrypi.com/documentation/computers/config_txt.html), `autoboot.txt` and tryboot
- [Raspberry Pi documentation PR 2701](https://github.com/raspberrypi/documentation/pull/2701/files), example of `tryboot_a_b` (a proposal, which may differ from the published text)
- [Mender community thread on autoboot.txt](https://hub.mender.io/t/using-autoboot-txt-on-raspberry-pi/6012), the atomicity caveat
- [Ubuntu A/B boot on Raspberry Pi](https://ubuntu.com/hardware/docs/boards/explanations/piboot-ab/), the watchdog approach
- [FOSDEM 2022: Bringing RAUC A/B Updates to More Linux Devices](https://archive.fosdem.org/2022/schedule/event/rauc_ab_updates/), `meta-rauc-community`
- [qbee tutorial: RAUC on Raspberry Pi 5](https://docs.qbee.io/tutorial-rpi5-rauc.html), U-Boot requirement
- [The Pi Hut: How do I power my Raspberry Pi?](https://thepihut.com/blogs/raspberry-pi-tutorials/how-do-i-power-my-raspberry-pi), GPIO power warning (a retailer guide, not official)
- [SparkFun: Raspberry Pi wall adapter](https://www.sparkfun.com/raspberry-pi-wall-adapter-power-supply-5-1vdc-3-0a-15-3w-usb-c.html), 5.1 V 3 A rating
