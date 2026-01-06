# VS Code Setup Guide for Options Trading App

This guide will walk you through setting up a Python virtual environment in VS Code for the Options Trading Dashboard application.

## Prerequisites

- **Python 3.8 or higher** installed on your system
- **Visual Studio Code** installed
- **Python extension** for VS Code (install from VS Code Extensions marketplace if not already installed)

## Step-by-Step Setup

### 1. Open the Project in VS Code

1. Open Visual Studio Code
2. Click `File` → `Open Folder...`
3. Navigate to and select the `schwabdev_app` folder
4. Click `Select Folder`

### 2. Create a Virtual Environment

#### Option A: Using VS Code Terminal (Recommended)

1. Open the integrated terminal in VS Code:
   - Press `` Ctrl+` `` (backtick) or
   - Go to `Terminal` → `New Terminal`

2. In the terminal, navigate to the project root:
   ```powershell
   cd C:\Users\<username>\Documents\options_trading_app\schwabdev_app
   ```

3. Create a virtual environment:
   ```powershell
   python -m venv venv
   ```
   
   This creates a `venv` folder in your project directory.

#### Option B: Using Command Palette

1. Press `Ctrl+Shift+P` to open the Command Palette
2. Type "Python: Create Environment"
3. Select "Python: Create Environment"
4. Choose "Venv"
5. Select your Python interpreter
6. The virtual environment will be created automatically

### 3. Activate the Virtual Environment

#### In VS Code Terminal:

**Windows PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows Command Prompt:**
```cmd
venv\Scripts\activate.bat
```

**Note:** If you get an execution policy error in PowerShell, run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

You should see `(venv)` at the beginning of your terminal prompt, indicating the virtual environment is active.

### 4. Select Python Interpreter in VS Code

1. Press `Ctrl+Shift+P` to open the Command Palette
2. Type "Python: Select Interpreter"
3. Select "Python: Select Interpreter"
4. Choose the interpreter from your `venv` folder:
   - Look for `.\venv\Scripts\python.exe` or
   - `Python 3.x.x ('venv': venv) ./venv/Scripts/python.exe`

VS Code will remember this selection for this workspace.

### 5. Install Dependencies

With the virtual environment activated, install the required packages:

```powershell
pip install --upgrade pip
pip install -r options_dashboard/requirements.txt
```

**Note:** If `requirements.txt` is missing some packages (like `customtkinter`), you may need to install them separately:

```powershell
pip install customtkinter
```

### 6. Verify Installation

Verify that packages are installed correctly:

```powershell
pip list
```

You should see packages like:
- pandas
- numpy
- scipy
- matplotlib
- altair
- customtkinter
- tksheet
- schwabdev

### 7. Run the Application

1. Make sure the virtual environment is activated (you should see `(venv)` in the terminal)
2. Navigate to the options_dashboard directory:
   ```powershell
   cd options_dashboard
   ```
3. Run the application:
   ```powershell
   python app.py
   ```

Alternatively, you can run it from the project root:
```powershell
python options_dashboard/app.py
```

## VS Code Configuration (Optional)

### Create a Launch Configuration

For easier debugging and running, create a VS Code launch configuration:

1. Create a `.vscode` folder in your project root (if it doesn't exist)
2. Create or edit `.vscode/launch.json`:
   ```json
   {
       "version": "0.2.0",
       "configurations": [
           {
               "name": "Python: Options Dashboard",
               "type": "python",
               "request": "launch",
               "program": "${workspaceFolder}/options_dashboard/app.py",
               "console": "integratedTerminal",
               "justMyCode": true,
               "env": {
                   "PYTHONPATH": "${workspaceFolder}"
               }
           }
       ]
   }
   ```

3. Press `F5` or go to `Run` → `Start Debugging` to run the app

### Create a Tasks Configuration

For quick terminal commands, create `.vscode/tasks.json`:

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Activate venv",
            "type": "shell",
            "command": "${workspaceFolder}/venv/Scripts/Activate.ps1",
            "problemMatcher": []
        },
        {
            "label": "Install dependencies",
            "type": "shell",
            "command": "pip install -r options_dashboard/requirements.txt",
            "options": {
                "cwd": "${workspaceFolder}"
            },
            "problemMatcher": []
        }
    ]
}
```

## Troubleshooting

### Virtual Environment Not Activating

- **PowerShell Execution Policy Error:**
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

- **Can't find venv:**
  - Make sure you're in the project root directory
  - Verify the `venv` folder exists
  - Try creating it again: `python -m venv venv`

### Python Interpreter Not Found

- Make sure Python is installed and in your PATH
- Check Python installation: `python --version`
- In VS Code, use `Ctrl+Shift+P` → "Python: Select Interpreter" to manually select it

### Import Errors

- Make sure the virtual environment is activated
- Verify packages are installed: `pip list`
- Reinstall requirements: `pip install -r options_dashboard/requirements.txt`
- Check that VS Code is using the correct Python interpreter

### Module Not Found Errors

- Ensure `PYTHONPATH` includes the project root
- Try running from the project root: `python -m options_dashboard.app`
- Check that all `__init__.py` files exist in package directories

## Quick Reference Commands

```powershell
# Create virtual environment
python -m venv venv

# Activate (PowerShell)
.\venv\Scripts\Activate.ps1

# Activate (CMD)
venv\Scripts\activate.bat

# Install dependencies
pip install -r options_dashboard/requirements.txt

# Run application
python options_dashboard/app.py

# Deactivate virtual environment
deactivate
```

## Best Practices

1. **Always activate the virtual environment** before running the app or installing packages
2. **Commit `venv` to `.gitignore`** (should already be done)
3. **Keep `requirements.txt` updated** when adding new dependencies
4. **Use the VS Code Python extension** for better IntelliSense and debugging
5. **Select the correct interpreter** before running or debugging

## Additional Resources

- [VS Code Python Documentation](https://code.visualstudio.com/docs/languages/python)
- [Python Virtual Environments Guide](https://docs.python.org/3/tutorial/venv.html)
- [VS Code Terminal Guide](https://code.visualstudio.com/docs/terminal/basics)

