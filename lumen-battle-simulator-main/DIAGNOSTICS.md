# Diagnósticos do Sistema e Ambiente de Execução

---

## 1. Verificações de Ambiente

| Componente | Verificação | Status |
|---|---|---|
| **Python** | Python 3.12.10 (64-bit) | PASS |
| **Pillow** | PIL v12.3.0 | PASS |
| **OpenCV** | OpenCV v5.0.0 | PASS |
| **PyAutoGUI** | PyAutoGUI com FailSafe=True | PASS |
| **Win32 API** | `user32.dll` e `kernel32.dll` via ctypes | PASS |
| **PyInstaller** | Compilação concluída em `dist/LumenaBot/LumenaBot.exe` | PASS |
| **Janela Alvo** | Detecção de títulos `Lumena.gg`, `Google Chrome`, `Chrome`, `Brave` | PASS (com Safety Guard se fechado) |
| **Entrada Física** | Win32 Scancodes + DirectInput + PostMessage + PyAutoGUI | PASS |

---

## 2. Como Executar os Diagnósticos

### Diagnóstico Completo de Ambiente
```powershell
& "C:\Users\02555331280\AppData\Local\Programs\Python\Python312\python.exe" scripts/validate_live_input.py
```

### Diagnóstico de Entrada Física e Foco de Janela
```powershell
& "C:\Users\02555331280\AppData\Local\Programs\Python\Python312\python.exe" scripts/test_physical_input.py
```
