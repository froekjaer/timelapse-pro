import SwiftUI

struct ContentView: View {
    @StateObject private var ble = BleTechnicianClient()
    @State private var totp = ""
    @State private var result = ""

    private let diagnostics = [
        "system.status", "camera.status", "camera.diagnostics", "camera.hardware.inventory",
        "camera.ptp.diagnostics", "modem.status", "modem.signal", "network.diagnostics",
        "storage.status", "certificate.trust.status"
    ]

    var body: some View {
        NavigationStack {
            Form {
                Section("Bluetooth") {
                    Label(ble.discovered ? "Edge fundet" : "Søger efter Edge", systemImage: ble.discovered ? "checkmark.circle.fill" : "antenna.radiowaves.left.and.right")
                        .foregroundStyle(ble.discovered ? .green : .secondary)
                    if let deviceName = ble.deviceName {
                        LabeledContent("Enhed", value: deviceName)
                    }
                    Button("Søg efter Edge") { ble.scan() }
                    Button("Afbryd") { ble.disconnect() }
                }

                Section("TOTP") {
                    SecureField("6-cifret kode", text: $totp)
                        .keyboardType(.numberPad)
                    Button("Log ind lokalt") { ble.authenticate(totp: totp) }
                        .disabled(!ble.discovered || totp.count != 6)
                    Label(ble.authenticated ? "Godkendt" : "Ikke godkendt", systemImage: ble.authenticated ? "lock.open.fill" : "lock.fill")
                }

                Section("Edge-status") {
                    if ble.status.isEmpty { Text("Afventer status") .foregroundStyle(.secondary) }
                    ForEach(ble.status.keys.sorted(), id: \.self) { key in
                        LabeledContent(key, value: String(describing: ble.status[key] ?? ""))
                    }
                }

                Section("Diagnostik") {
                    ForEach(diagnostics, id: \.self) { operation in
                        Button(operation) {
                            ble.call(operation: operation) { response in
                                switch response {
                                case .success(let value): result = String(describing: value)
                                case .failure(let error): result = error.localizedDescription
                                }
                            }
                        }
                        .disabled(!ble.authenticated)
                    }
                    if !result.isEmpty { Text(result).font(.caption).textSelection(.enabled) }
                }

                if let lastError = ble.lastError { Section { Text(lastError).foregroundStyle(.red) } }
            }
            .navigationTitle("TimeLapse Technician")
        }
    }
}
