# Changelog

## v0.2.5

Fixed an issue where the `device_class` registered with `DeviceProxy()` did not reference the `.pyi` type stubs, preventing editor autocompletion from working correctly.

## v0.2.4

Starting the server and client on addresses other than `127.0.0.1` exposed several bugs, which have been fixed.

### Changed

- Fixed configuration-related bugs by comprehensively reorganizing configuration handling:
  - Clarified that `Config` is an object that holds configuration information.
  - Centralized responsibility for loading YAML in `Config`.
  - Reorganized Control / SCPI / Worker so that they accept only a `Config` object or constructor arguments.
  - When `Config` is not used, operation relies solely on constructor arguments.
  - Explicit constructor arguments take precedence over settings in `Config`.

- Fixed network configuration bugs:
  - Standardized on `SERVER_HOST` as the canonical name.
  - Continued support for `SERVER_IP` for backward compatibility.
  - Standardized on `host` as the canonical constructor argument.
  - Continued support for `ip` for backward compatibility.

- Reorganized example programs:
  - Discontinued passing YAML files directly.
  - Standardized on creating and using a `Config` object.

- Reorganized server startup:
  - Obtain `SERVER_HOST` / `SERVER_PORT` from the `Config` object.
  - Ensure that logged startup settings match the actual server configuration.

### Fixed

- Fixed inconsistent configuration lookup caused by mixing `SERVER_HOST` and `SERVER_IP`.
- Fixed differences in configuration resolution between `Config` and constructor-based initialization.
- Fixed a mismatch between the port reported in logs and the actual listening port at server startup.
- Fixed inconsistencies in configuration passing between Client / Control / Worker.

### Docs

- Updated the configuration instructions.
- Clarified the responsibilities of `Config` and the roles of the individual layers.
- Documented `SERVER_HOST` as the canonical name.

## v0.2.3

### Changed

- Improved range selection in the control API:
  - `set_range()` now supports both physical quantities and range indices.
  - Changed the API to accept mutually exclusive `value` and `index` arguments.
  - Removed the separate range-index API and consolidated its functionality into `set_range()`.

- Improved accepted range input formats:
  - Added support for strings with units, including:
    - `"500mV"`
    - `"500 mV"`
    - `"5V"`
    - `"5 V"`
    - `"50kΩ"`
    - `"50 kOhm"`, etc.
  - Numeric inputs are interpreted in the base unit of the current measurement mode:
    - DCV / ACV: V
    - DCI / ACI: A
    - Resistance: Ω
    - Capacitance: F

- Moved range conversion to the Control layer:
  - Kept the SCPI layer as a thin wrapper aligned with the hardware specification.
  - The Control layer now converts physical quantities into discrete SCPI range indices.

- Improved range validation:
  - Detect ranges that are incompatible with the current measurement mode.
  - Disallow specifying `value` and `index` simultaneously.

- Updated the API documentation:
  - Updated the Control API reference to reflect the current implementation.
  - Updated the Control Layer documentation.
  - Added a mapping table between hardware specifications and the Control API.
  - Added lists of measurement modes, ranges, and measurement rates.

### Added

- Hardware specification documentation:
  - Measurement modes supported by the XDM1241.
  - Available ranges for each measurement mode.
  - Measurement rates.
  - Corresponding Control APIs.

## v0.2.2

### Changed

- Improved the synchronous and asynchronous client API design:
  - Organized Sync clients as synchronous APIs and Async clients as asynchronous APIs for natural use.
  - Supported an implementation in which framework-generated methods do not overwrite device-specific methods.

- Improved the asynchronous measurement API:
  - Retained client-side polling in `wait_until_done()`.
  - Retained the ability for other clients to query status, stop measurements, and retrieve results while the server continues measuring.

- Improved worker controllability:
  - Improved worker state management so control requests can be handled during asynchronous measurements.
  - Further separated measurement and control processing, taking multiple clients into account.

- Reorganized logging:
  - Removed unnecessary client-side logging for frequently called status-monitoring APIs.
  - Clarified the division of responsibilities with server-side access logs.

## v0.2.1

### Changed

- Revised the asynchronous measurement API:
  - Changed `wait_until_done()` to use client-side polling.
  - Reorganized the server so that other clients can query status while measurements continue.
- Improved asynchronous measurement processing in the worker:
  - Revised the design to handle `is_running()`, `stop()`, and `get_result()` even during measurement.
  - Improved coexistence between the worker event loop and control requests.
- Clarified API behavior:
  - Organized the API so that the same interface can be used for local and server execution.
  - Clarified asynchronous measurement state transitions.

### Added

- `is_running()`
- `wait_until_done()`
- `stop()`
- `get_result()`
- Example programs for asynchronous measurement.
- An asynchronous measurement tutorial.

### Fixed

- Fixed an issue preventing other clients from controlling the device during asynchronous measurement.
- Fixed asynchronous measurement result retrieval.
- Fixed worker job management.

## v0.2.0

### Changed

- Comprehensively revised the high-level API:
  - Reorganized it around the stateful `set_mode()` API.
  - Centralized measurement condition management between ctrl and worker.
  - Organized `meas()` / `meas_continue()` to use stored settings.
- Reorganized the FastAPI public API:
  - Revised request / response models and restructured the API.
  - Standardized API names, arguments, and return values.
- Revised the worker architecture:
  - The worker retains configuration state and synchronizes with ctrl through shared state.
  - Reorganized the worker's configuration cache to match the API specification.
- Revised clients:
  - Aligned Sync / Async clients with `API_SPEC`.
  - Established `DeviceProxy("Xdm1000Ctrl", ...)` as the canonical usage pattern.
  - Reorganized connection settings so they can be shared through `config`.

### Fixed

- Fixed inconsistencies between ctrl / worker / client following the comprehensive API changes.
- Fixed errors occurring after repeated Sync client API calls:
  - `Event loop is closed`
  - `cannot reuse already awaited coroutine`
- Changed the Sync client to retain a dedicated event loop and reuse the same `httpx.AsyncClient`.
- Improved stability when using `DeviceProxy(sync)`.
- Updated examples to reflect the API changes.

### Docs

- Comprehensively updated the API documentation.
- Updated the README to match the API specification.
- Updated sample code to use the new API.

## v0.1.2

- Improved documentation.

## v0.1.1

- Improved documentation.

## v0.1.0

### Changed

- Revised configuration handling:
  - Reorganized configuration around `Config` in `config.py` and YAML files.
  - When `config` is supplied, settings such as `PORT` / `TIMEOUT` / `BAUDRATE` take precedence.
  - When `config` is not supplied, settings can be provided through constructor arguments.
- Revised the control architecture:
  - Clarified the responsibilities of ctrl / worker / scpi.
  - Made it possible to choose whether to use a separate process.
  - When a separate process is used, the worker owns the serial port while the parent ctrl manages state and RPC.
- Revised measurement condition handling:
  - Conditions stored by `set_meas_mode()` can be reused by `meas()` / `meas_xxx()`.
  - Arguments supplied to a `meas(...)` call take precedence, while unspecified settings are inherited from stored conditions.
  - Avoid unnecessary retransmission of `CONFigure` / `RATE` when measurement conditions are unchanged.
- Revised integration with `ese774_frame`:
  - Added a registration path for using `DeviceProxy("Xdm1000Ctrl", ...)` from `server_fastapi`.
  - Revised Sync / Async client constructors to accept `config` as an entry point for transparent clients.
- Revised examples and testing paths:
  - Retained `main()` in ctrl / scpi for standalone operation checks.
  - Made it easier to verify both direct execution and process-based execution.

### Fixed

- Fixed interface inconsistencies between ctrl / worker / scpi.
- Fixed timeout-related problems caused by insufficient `worker_ready` synchronization immediately after worker startup.
- Fixed runtime errors caused by an uninitialized measurement-condition cache in the worker.
- Fixed runtime errors during worker imports, including a missing `typing.Union` import.
- Revised arguments to pyserial `Serial(...)` to reduce type errors.
- Fixed client constructor inconsistencies when accessed through `DeviceProxy`.
- Revised code that was incompatible with Python 3.6.

### Docs

- Reviewed docstrings and comments throughout the project.
- Added explanations of architectural policy, measurement modes, and worker responsibilities.

## v0.0.1

- Made minor documentation improvements and additions.
- Fixed ctrl measurement methods that called setters such as `set_voltage` on every invocation:
  - When measurement arguments are unchanged, the SCPI side no longer reapplies the settings.

## v0.0.0

Initial release.

### Added

- Xdm1000Ctrl
- Xdm1000Scpi
- multiprocessing worker
- one-shot measurement
- pseudo continuous measurement
- statistics mode
- FastAPI server
- ese774_frame integration
- Sync/Async client
- measurement state management
- examples
- documentation
