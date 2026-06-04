# Senso4s BLE Protocol

This document describes the observed BLE protocol used by the [Senso4s](https://senso4s.com/) propane gas cylinder sensor. It is written to be independent of any programming language or implementation framework.

## Scope

This document summarizes protocol details inferred from the public repository implementation and is intended for future reuse in embedded, mobile, desktop, or server applications.

It covers:

- passive monitoring via BLE advertisements
- manufacturer-specific data layout
- known value encodings
- known GATT UUIDs referenced by the implementation
- additional observed characteristic payload formats

It does not claim to be an official vendor specification.

## Device Identification

Known identifiers for Senso4s devices:

- Device name: `SENSO4S`
- Known BLE manufacturer IDs:
  - `0x0059`
  - `0x09CC`

A receiver should treat advertisements using either manufacturer ID as potentially belonging to a Senso4s device.

## BLE Advertisement Format

The implementation parses manufacturer-specific data from BLE advertisements.

### Manufacturer Data Layout

| Offset | Size | Field | Description |
|---|---:|---|---|
| 0 | 1 | `flags` | Model marker in upper nibble, usage mode in lower nibble |
| 1 | 1 | `level_or_status` | Gas percentage or special status code |
| 2 | 1 | `reserved_2` | Unknown / undocumented |
| 3 | 1 | `reserved_3` | Unknown / undocumented |
| 4 | 1 | `battery_raw` | Raw battery percentage |
| 5 | 1 | `reserved_5` | Unknown / undocumented |
| 6 | 6 | `mac_address` | Device MAC address embedded in the frame |

### Frame Length

A practical decoder should require at least **12 bytes** of manufacturer data to fully decode the known fields.

## Flags Byte

The `flags` byte is split into two 4-bit nibbles:

- upper nibble: model marker
- lower nibble: usage mode

### Model Marker

Observed behavior indicates:

- upper nibble `0x8` => Basic model
- any other upper nibble => Plus model

This should be treated as an implementation-derived rule, not an official published protocol guarantee.

### Usage Mode

The lower nibble encodes usage mode.

| Value | Meaning |
|---:|---|
| 1 | BBQ |
| 2 | Camping |
| 3 | Caravanning |
| 4 | Heating |
| 5 | Household |

Unknown values should be treated as undefined. One implementation falls back to `Household` when an unknown value is encountered, but that fallback is application behavior rather than protocol definition.

## Level or Status Byte

The `level_or_status` byte may represent either a normal gas level percentage or a special code.

### Normal Gas Level

| Range | Meaning |
|---:|---|
| 0..100 | Gas level percentage |

### Anomaly Encoding

| Range | Meaning |
|---:|---|
| 241..247 | Anomaly bitfield encoded as `value - 240` |

Anomaly flag bit meanings:

| Bit Value | Meaning |
|---:|---|
| 1 | Temperature anomaly |
| 2 | Incline anomaly |
| 4 | Motion anomaly |

Examples:

| Raw Value | Decoded Flag Value | Meaning |
|---:|---:|---|
| 241 | 1 | Temperature |
| 242 | 2 | Incline |
| 243 | 3 | Temperature + Incline |
| 244 | 4 | Motion |
| 247 | 7 | Temperature + Incline + Motion |

### Error and Calibration Codes

| Value | Meaning |
|---:|---|
| 251 | Measurement error |
| 252 | Scale error |
| 253 | Sensor error |
| 254 | Battery critically low |
| 255 | Calibration required |

### Other Values

Values greater than `100` that are not in the anomaly or error/calibration ranges should be treated as invalid, unknown, or reserved.

## Battery Field

The `battery_raw` byte is interpreted as a battery percentage.

Protocol-level recommendation:

- preserve the raw value if possible
- any rounding should be considered presentation logic, not protocol logic

One observed implementation rounds the battery value up to the nearest 5%, but this should be considered optional UI behavior.

## MAC Address Field

The advertisement includes a 6-byte MAC address at offsets `6..11`.

For display, it may be formatted as six hexadecimal octets separated by colons, for example:

`AA:BB:CC:DD:EE:FF`

## Passive Monitoring Recommendations

A passive BLE monitor should:

1. scan BLE advertisements
2. inspect manufacturer-specific data
3. accept manufacturer IDs `0x0059` and `0x09CC`
4. require at least 12 bytes of payload for complete decoding
5. decode:
   - `flags`
   - `level_or_status`
   - `battery_raw`
   - `mac_address`
6. treat bytes `2`, `3`, and `5` as reserved unless independently verified

## Known GATT UUIDs

The implementation also references active BLE GATT communication. These are included for completeness.

### Service UUIDs

| Type | UUID |
|---|---|
| Primary service | `00007081-a20b-4d4d-a4de-7f071dbbc1d8` |
| Scan filter UUID | `00007081-0000-1000-8000-00805f9b34fb` |

### Characteristic UUIDs

| Purpose | UUID |
|---|---|
| Level | `00007082-a20b-4d4d-a4de-7f071dbbc1d8` |
| Cylinder configuration | `00007083-a20b-4d4d-a4de-7f071dbbc1d8` |
| History | `00007085-a20b-4d4d-a4de-7f071dbbc1d8` |
| Calibration | `00007086-a20b-4d4d-a4de-7f071dbbc1d8` |
| Setup date | `00007087-a20b-4d4d-a4de-7f071dbbc1d8` |

## Additional Observed Characteristic Payloads

The following formats are included because they were explicitly encoded/decoded in the implementation.

### Cylinder Configuration Characteristic

Observed length: **5 bytes**

| Offset | Size | Field | Encoding |
|---|---:|---|---|
| 0 | 2 | Empty weight | Little-endian signed 16-bit integer, divided by 100 gives kilograms |
| 2 | 2 | Gas capacity | Little-endian signed 16-bit integer, divided by 100 gives kilograms |
| 4 | 1 | Usage mode | Same value set as advertisement usage mode |

### Setup Date Characteristic

Observed length: **7 bytes**

| Offset | Size | Field | Encoding |
|---|---:|---|---|
| 0 | 2 | Year | Little-endian unsigned 16-bit integer |
| 2 | 1 | Month | 1..12 |
| 3 | 1 | Day | 1..31 |
| 4 | 1 | Hour | 0..23 |
| 5 | 1 | Minute | 0..59 |
| 6 | 1 | Second | 0..59 |

Special case:

- all-zero payload means date not set

### History Characteristic

Observed payload structure: repeated **4-byte records**

Per-record layout:

| Offset | Size | Field | Encoding |
|---|---:|---|---|
| 0 | 2 | Remaining mass | Little-endian signed 16-bit integer, divided by 100 gives kilograms |
| 2 | 2 | Cycle count delta | Little-endian signed 16-bit integer |

Observed timing rule:

- one cycle corresponds to **15 minutes**
- timestamps can be derived from the setup date plus cumulative cycle count

## Suggested Language-Independent Decoding Rules

### Advertisement Decoding

1. Verify manufacturer ID is `0x0059` or `0x09CC`
2. Verify payload length is at least 12 bytes
3. Read:
   - byte 0 as `flags`
   - byte 1 as `level_or_status`
   - byte 4 as `battery_raw`
   - bytes 6..11 as `mac_address`
4. Decode `flags`:
   - upper nibble = model marker
   - lower nibble = usage mode
5. Decode `level_or_status`:
   - `0..100` => gas percentage
   - `241..247` => anomaly flags
   - `251..254` => error code
   - `255` => calibration required

## Unknown / Reserved Fields

The meaning of advertisement bytes at offsets:

- `2`
- `3`
- `5`

is not established by the observed implementation and should be treated as reserved.

## Status of This Document

This document reflects observed behavior from an implementation, not an official vendor protocol publication.

Before relying on undocumented fields or assuming long-term compatibility, validate behavior with packet captures or vendor documentation.

## Source

Derived from analysis of the original repository:

- `ksanislo/senso4s_ble`: `https://github.com/ksanislo/senso4s_ble`
