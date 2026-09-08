# TimeLapse Technician iPhone client

`TimeLapseTechnicianApp.swift` and `ContentView.swift` form the minimal native
technician app. `BleTechnicianClient.swift` is the CoreBluetooth transport layer for the
native technician app. It discovers the Edge GATT service, authenticates with
the six-digit TOTP, subscribes to status/response notifications, and dispatches
Service Operation requests. UI screens must remain thin and call this client;
they must not contain camera, modem, GPIO, shell or system-service logic.

The files are intentionally kept separate from the web UI. Add them to an Xcode
iOS app target with `NSBluetoothAlwaysUsageDescription` and distribute
through the normal signed/TestFlight process before it can be used on an
iPhone. The project definition is in `ios/project.yml`; `xcodegen` generates
`ios/TimeLapseTechnician.xcodeproj`. Select an Apple development team in Xcode,
connect the iPhone, and run the target for a direct install or archive it for
TestFlight. The current Mac has full Xcode, but no iOS simulator runtime or
connected iPhone has yet been supplied, so no signed build has been produced.
