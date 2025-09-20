# Astro Dwarf Scheduler

Astro Dwarf Scheduler is a comprehensive tool designed to automate imaging sessions for Dwarf II and Dwarf III devices. It provides both GUI and console interfaces for creating, managing, and executing astronomical imaging sessions with advanced scheduling capabilities.

<img width="812" height="832" alt="Screenshot 2025-09-14 233515" src="https://github.com/user-attachments/assets/f059393c-19d7-4026-b04d-69ddb28f0ca0" />


## Features

### Core Functionality
- **Automated Session Management**: Processes JSON session files based on scheduled times
- **Multi-Device Support**: Full compatibility with Dwarf II and Dwarf III telescopes
- **Flexible Connectivity**: Supports both Bluetooth and Wi-Fi connections
- **Cross-Platform**: Works on Windows, macOS, and Linux

### GUI Application (`astro_dwarf_session_UI.py`)
The modern GUI provides six comprehensive tabs:

#### 📋 **Main Tab**
- **Multi-Configuration Support**: Manage multiple telescope setups
- **Real-Time Video Preview**: Live MJPEG stream from telescope
- **Session Monitoring**: Live session info with runtime tracking and countdowns
- **Connection Management**: Bluetooth/Wi-Fi connection controls
- **Scheduler Controls**: Start/stop scheduler, calibration, polar alignment
- **Session Statistics**: Real-time file counts for ToDo/Current/Done/Error/Results

#### ⚙️ **Settings Tab**
- **Device Configuration**: Telescope type, camera settings, imaging parameters
- **Location Services**: Automatic location detection and manual coordinates
- **Path Management**: Stellarium integration, session directories
- **UI Preferences**: Display brightness and interface customization

#### 🆕 **Create Session Tab**
- **Manual Session Creation**: Target coordinates, imaging parameters, scheduling
- **CSV Import Support**: 
  - Stellarium CSV format
  - Telescopius mosaic planning files
- **Real-Time Stellarium Integration**: Fetch current target from Stellarium
- **Smart Validation**: Comprehensive session data validation
- **Multiple Target Types**: Solar system objects, manual coordinates, or no goto

#### 👁️ **Overview Session Tab**
- **Session Queue Management**: Visual session pipeline (ToDo → Current → Done/Error)
- **Real-Time Monitoring**: Live video feed with frame capture
- **Session Details**: Complete session information display
- **Queue Operations**: Move, delete, and organize sessions
- **Execution Controls**: Start/stop individual or batch sessions

#### 📊 **Results Session Tab**
- **Automated Analysis**: JSON to CSV conversion by observation night
- **Success/Error Tracking**: Separate views for completed and failed sessions
- **Session Statistics**: Exposure counts, timing, equipment settings
- **Data Export**: CSV format for further analysis
- **Historical Data**: Organized by observation date

#### ✏️ **Edit Sessions Tab**
- **Live Session Editing**: Modify existing session files
- **Form-Based Interface**: User-friendly parameter adjustment
- **Bulk Operations**: Select and modify multiple sessions
- **Real-Time Validation**: Immediate feedback on changes

### Advanced Features
- **Directory Auto-Creation**: Intelligent session folder management
- **Error Recovery**: Robust error handling and session retry logic
- **Time Zone Support**: Proper handling of observation scheduling
- **Configuration Backup**: Safe configuration management
- **Video Stream Management**: Efficient MJPEG streaming with proper cleanup
- **Memory Management**: Optimized video streaming and UI updates
- **Thread Safety**: Proper multi-threaded operation
- **Cross-Platform Paths**: Proper path handling for all operating systems

## Installation

### Prerequisites
- Python 3.8 or higher
- Windows 10/11, macOS 10.15+, or modern Linux distribution

### Quick Setup
1. Download or clone this project to your local machine

2. Install the required Python libraries:
   ```sh
   python -m pip install -r requirements.txt
   python -m pip install -r requirements-local.txt --target .
   ```
   > **Note**: The `dwarf_python_api` library must be installed locally in the root path of this project using the `--target .` parameter.

3. **Optional**: Install video preview dependencies:
   ```sh
   pip install Pillow requests
   ```

4. Configure the `config.ini` file with your Wi-Fi SSID and password to use your Dwarf on your local Wi-Fi network.

### Starting the Application

#### GUI Version (Recommended)
```sh
python astro_dwarf_session_UI.py
```

#### Console Version
```sh
python astro_dwarf_scheduler.py
```

For console version with parameters:
```sh
python astro_dwarf_scheduler.py --ip ip_value --id (2 or 3)
```

## Usage

### Getting Started
1. **Configure Settings**: Use the Settings tab to set up your telescope and location
2. **Create Sessions**: Use the Create Session tab or import CSV files
3. **Monitor Progress**: Use the Overview tab to watch sessions execute
4. **Review Results**: Check the Results tab for session analysis

### Session File Management
- Session files are automatically organized in `./Astro_Sessions/` subdirectories:
  - `ToDo/`: Sessions waiting to be processed
  - `Current/`: Currently executing session
  - `Done/`: Successfully completed sessions
  - `Error/`: Failed sessions for review
  - `Results/`: CSV analysis files organized by night

### Multi-Device Setup
The application supports multiple telescope configurations:
1. Enable "Multiple" mode in the Main tab
2. Create named configurations for different telescopes
3. Each configuration maintains separate session directories
4. Switch between configurations seamlessly

### Stellarium Integration
- Real-time target fetching from Stellarium
- Automatic coordinate conversion
- Object identification and description
- Seamless workflow integration

### CSV Import Formats
#### Stellarium CSV
```csv
Name,RA,Dec,Magnitude,Type
M31,00:42:44.3,+41:16:09,3.4,Galaxy
```

#### Telescopius Mosaic
```csv
Pane,RA,DEC,Description
1,00:42:44.3,+41:16:09,M31 Pane 1
```

## Troubleshooting

### Connection Issues
- If Bluetooth fails, the application will prompt for connection attempts
- Wi-Fi parameters can be set via command line for headless operation
- Use the Dwarfium app to establish initial connection if needed

### Configuration Issues
- **Dwarf ID Inconsistency Fix**: The system handles dwarf_id values differently between Bluetooth and IP connections:
  - **Device returns actual ID**: Dwarf II = 2, Dwarf III = 3
  - **Config stores offset ID**: Dwarf II = 1, Dwarf III = 2
  - **Bluetooth connection**: Correctly sends offset values
  - **IP connection**: Now converts actual device ID to offset before storing
  - **Result**: Consistent dwarf_id handling across all connection methods

### Video Preview Issues
- Install `Pillow` and `requests` if video preview shows installation message
- Check network connectivity to telescope IP
- Video stream URL: `http://{DWARF_IP}:8092/mainstream`

### Session Management
- Ensure proper permissions for session directories
- Check that JSON session files are properly formatted
- Review error logs for detailed troubleshooting information

## Architecture

### File Structure
```
astro_dwarf_session/
├── astro_dwarf_session_UI.py    # Main GUI application
├── astro_dwarf_scheduler.py     # Console scheduler
├── config.py                    # Configuration management
├── dwarf_session.py            # Session execution logic
├── tabs/                       # GUI tab modules
├── Astro_Sessions/             # Session data directories
└── dwarf_python_api/           # Telescope API
```

### Session Workflow
1. **Creation** → Sessions created in ToDo folder
2. **Scheduling** → Automatic processing based on scheduled time
3. **Execution** → Moved to Current during processing
4. **Completion** → Moved to Done (success) or Error (failure)
5. **Analysis** → Automatically analyzed into Results CSV files

## Contributing

We welcome contributions! The codebase includes comprehensive error handling, logging, and cross-platform compatibility.

## Notes
- Clear skies and good luck! The Dwarf will work for you.
- The application automatically manages session directories and file organization.
- All configuration changes are applied immediately without restart required.
