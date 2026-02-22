# Quantum-Safe Tactical Communication System

## Prerequisites
- Python 3.8+ (Tested with 3.14)
- Pip installed

## Installation
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *Note: If `qiskit` installation fails, the simulator works in classical emulation mode.*

## Running the Demo

### 1. Console Demo (Quick Test)
Run the full scenario in your terminal:
```bash
python main.py
```
This simulates:
- Soldier A requesting a key
- Key generation (BB84)
- Encrypted message transfer to Soldier B
- Attack simulation (Eve detection)

### 2. Interactive Dashboard (Full UI)
Launch the web interface:
```bash
streamlit run dashboard/dashboard_ui.py
```
Capabilities:
- Click **Get Key A** to generate keys.
- Toggle **Eve Attacking?** to simulate eavesdropping.
- Send messages and see the QBER (Quantum Bit Error Rate) change.
- Visualize the link status (Green/Red).

## Testing
Run the verification tests:
```bash
python -c "import sys, os; sys.path.insert(0, os.getcwd()); import unittest; from tests import test_kms_devices; suite = unittest.TestLoader().loadTestsFromModule(test_kms_devices); unittest.TextTestRunner(verbosity=2).run(suite)"
```
