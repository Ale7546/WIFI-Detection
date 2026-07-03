# Create virtual environment if it doesn't exist
if (-not (Test-Path -Path ".venv")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv .venv
} else {
    Write-Host "Virtual environment already exists."
}

# Upgrade pip and install requirements
Write-Host "Upgrading pip..."
& .venv\Scripts\python.exe -m pip install --upgrade pip

Write-Host "Installing requirements..."
& .venv\Scripts\pip.exe install -r requirements.txt

Write-Host "Environment setup complete!"
