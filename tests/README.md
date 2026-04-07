# TimeLapse Pro — Testscripts

## Oversigt

| Fil | Type | Beskrivelse |
|-----|------|-------------|
| test_agent_integrity.py | Unit | Verificerer agent.py kode integritet |
| test_headend_endpoints.py | Unit | Verificerer headend main.py endpoints |
| test_api_integration.py | Integration | Live API tests mod staging headend |

## Kørsel

```bash
# Alle unit tests (ingen netværk kræves)
pytest tests/test_agent_integrity.py tests/test_headend_endpoints.py -v

# Integration tests (kræver headend på 192.168.86.132)
pytest tests/test_api_integration.py -v

# Alle tests
pytest tests/ -v
```

## I GitHub Actions

Unit tests køres automatisk ved hver push.
Integration tests køres manuelt eller mod staging.

## Kendte fejl der testes

1. _sync_captures limit=100 (ikke 20)
2. _sync_captures i capture cycle
3. _sync_captures INFO logging
4. /api/lab/params endpoint
5. /api/lab/get-params endpoint
6. device_config i API response
7. lab_camera_ready reset
8. Thumbnail størrelse > 1000 bytes
9. config_interval = 5 minutter
10. Ingen duplikerede imports
