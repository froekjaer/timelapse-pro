import CoreBluetooth
import Foundation
import Combine

/// BLE transport client. UI code should render these results and never call
/// camera, modem, GPIO or system services directly.
final class BleTechnicianClient: NSObject, ObservableObject {
    static let serviceUUID = CBUUID(string: "6F2B0001-2F4E-4A8C-9B6E-74696D656C70")
    private let authUUID = CBUUID(string: "6F2B0002-2F4E-4A8C-9B6E-74696D656C70")
    private let requestUUID = CBUUID(string: "6F2B0003-2F4E-4A8C-9B6E-74696D656C70")
    private let responseUUID = CBUUID(string: "6F2B0004-2F4E-4A8C-9B6E-74696D656C70")
    private let statusUUID = CBUUID(string: "6F2B0005-2F4E-4A8C-9B6E-74696D656C70")

    @Published private(set) var discovered = false
    @Published private(set) var deviceName: String?
    @Published private(set) var authenticated = false
    @Published private(set) var status: [String: Any] = [:]
    @Published private(set) var lastError: String?

    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var authCharacteristic: CBCharacteristic?
    private var requestCharacteristic: CBCharacteristic?
    private var responseCharacteristic: CBCharacteristic?
    private var statusCharacteristic: CBCharacteristic?
    private var responseHandler: ((Result<[String: Any], Error>) -> Void)?

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: .main)
    }

    func scan() {
        guard central.state == .poweredOn else { return }
        lastError = nil
        central.scanForPeripherals(withServices: [Self.serviceUUID], options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
    }

    func disconnect() {
        if let peripheral { central.cancelPeripheralConnection(peripheral) }
    }

    func authenticate(totp: String) {
        guard let authCharacteristic, totp.count == 6, totp.allSatisfy(\.isNumber) else {
            lastError = "BLE ikke klar eller TOTP er ugyldig"
            return
        }
        write(["type": "totp", "code": totp], to: authCharacteristic)
    }

    func call(operation: String, params: [String: Any] = [:], completion: @escaping (Result<[String: Any], Error>) -> Void) {
        guard authenticated, let requestCharacteristic else {
            completion(.failure(ClientError.notAuthenticated))
            return
        }
        let id = UUID().uuidString
        responseHandler = completion
        write(["id": id, "operation": operation, "params": params], to: requestCharacteristic)
    }

    private func write(_ object: [String: Any], to characteristic: CBCharacteristic) {
        guard JSONSerialization.isValidJSONObject(object),
              let data = try? JSONSerialization.data(withJSONObject: object),
              data.count <= 8192,
              let peripheral else { return }
        peripheral.writeValue(data, for: characteristic, type: .withResponse)
    }

    private enum ClientError: Error { case notAuthenticated, invalidResponse }
}

extension BleTechnicianClient: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn { scan() }
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                        advertisementData: [String: Any], rssi RSSI: NSNumber) {
        self.peripheral = peripheral
        deviceName = peripheral.name
        peripheral.delegate = self
        central.stopScan()
        central.connect(peripheral)
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        discovered = true
        peripheral.discoverServices([Self.serviceUUID])
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        discovered = false
        authenticated = false
        deviceName = nil
        authCharacteristic = nil
        requestCharacteristic = nil
        responseCharacteristic = nil
        statusCharacteristic = nil
        responseHandler = nil
        if let error { lastError = error.localizedDescription }
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        discovered = false
        if let error { lastError = error.localizedDescription }
        else { lastError = "Kunne ikke oprette BLE-forbindelse" }
    }
}

extension BleTechnicianClient: CBPeripheralDelegate {
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard error == nil, let service = peripheral.services?.first(where: { $0.uuid == Self.serviceUUID }) else { return }
        peripheral.discoverCharacteristics([authUUID, requestUUID, responseUUID, statusUUID], for: service)
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard error == nil else { lastError = error?.localizedDescription; return }
        for characteristic in service.characteristics ?? [] {
            switch characteristic.uuid {
            case authUUID: authCharacteristic = characteristic
            case requestUUID: requestCharacteristic = characteristic
            case responseUUID:
                responseCharacteristic = characteristic
                peripheral.setNotifyValue(true, for: characteristic)
            case statusUUID:
                statusCharacteristic = characteristic
                peripheral.setNotifyValue(true, for: characteristic)
            default: break
            }
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard error == nil, let data = characteristic.value,
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            lastError = error?.localizedDescription ?? "Ugyldigt BLE-svar"
            return
        }
        if characteristic.uuid == statusUUID {
            status = object
        } else if characteristic.uuid == responseUUID {
            if object["id"] as? String == "auth" {
                authenticated = object["ok"] as? Bool == true
            } else if let responseHandler {
                self.responseHandler = nil
                if object["ok"] as? Bool == true { responseHandler(.success(object)) }
                else { responseHandler(.failure(ClientError.invalidResponse)) }
            }
        }
    }
}
