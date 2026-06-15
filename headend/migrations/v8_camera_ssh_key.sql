-- Migration v8: SSH keypair + reverse tunnel port per kamera
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS ssh_private_key   TEXT    DEFAULT NULL;
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS ssh_public_key    TEXT    DEFAULT NULL;
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS reverse_tunnel_port INTEGER DEFAULT NULL;
