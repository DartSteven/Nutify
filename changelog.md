# Nutify Changelog

## Version 0.2.0 (2026 - Internal Testing)

* **Frontend Migration To React SPA**
* **Setup Wizard Profile And Topology Flow**
* **Multi-UPS Runtime Integration**
* **Unified Multi-Target Data Storage**
* **Settings Information Architecture Split**
* **Operations Runtime Formulas (New)**
* **Canonical Variable Remapper Improvements**
* **Reports And Notifications Scope Enhancements**
* **Runtime And Service Hardening**
* **Container And Build Pipeline Updates**
* **OpenID Connect Single Sign-On (SSO)**: Optional, provider-agnostic OIDC login, additive to local authentication:
  * Group-based role mapping via `OIDC_ADMIN_GROUP` and an optional `OIDC_USER_GROUP` that also gates who may sign in
  * Optional `OIDC_AUTO_REDIRECT` to the provider, with a `/auth/login?local=1` escape hatch for the local administrator


## Version 0.1.7 (07/07/2025)

* **User Authentication System**: Implemented multi-user login functionality:
  * Added administrator and user roles
  * Administrator: Full access to all features and configurations
  * User: Configurable permissions for individual pages and options tabs
  * Admin can selectively grant users access to specific dashboard pages (energy, power, commands, etc.)
  * Admin can selectively grant users access to specific options tabs (email, webhooks, advanced, database, etc.)
  * Secure password handling and session management with automatic timeout

* **Enhanced Setup Wizard**: Improved initial configuration experience:
  * Fixed button alignment in Admin Setup step (Next button now properly aligned to right)
  * Corrected button visibility in Review step (Next button no longer appears after Test Connection)
  * Improved user interface consistency across all setup steps
  * Enhanced wizard navigation and visual feedback

* **Authentication System Improvements**:
  * Removed unnecessary "Back to Dashboard" link from login page for better UX
  * Streamlined login interface for cleaner user experience
  * Enhanced password security with proper encryption and validation
  * Added secure session management with automatic timeout

* **Database Schema Enhancements**:
  * Added new user authentication table for login management
  * Implemented secure password storage with hashing
  * Added user role and permission tracking
  * Enhanced data validation and error handling

* **System Stability Improvements**:
  * Moved to NUT 2.8.3 for improved hardware compatibility and stability
  * Rebuilt core architecture for enhanced performance and reliability
  * Added comprehensive admin and user account management system
  * Fixed configuration editor expansion/collapse state persistence across page navigation
  * Improved error handling for incorrect password scenarios with automatic table cleanup

* **Reporting System Enhancements**:
  * Fixed time and battery report generation issues
  * Added new pandas-based data processing for improved report accuracy
  * Enhanced report formatting and data visualization
  * Improved report scheduling and delivery mechanisms

* **Bug Fixes and UI Improvements**:
  * Fixed config editor state management in Advanced settings
  * Resolved navigation issues when switching between configuration tabs
  * Improved JavaScript module loading and error handling
  * Enhanced responsive design across all interface components
  * Fixed various CSS and layout inconsistencies

* **Security Enhancements**:
  * Added user authentication requirement for accessing configuration areas
  * Implemented secure password hashing and storage
  * Added session management with automatic timeout
  * Enhanced input validation and sanitization

## Version 0.1.6 (15/04/2025)

* **Setup Wizard**: Added comprehensive setup wizard:
  * Step-by-step configuration for new installations
  * Automatic NUT configuration without manually editing docker-compose
  * Guided UPS setup with driver selection assistance
  * Intelligent detection of existing UPS devices

* **System Resource Monitoring**: Added real-time system monitoring:
  * CPU usage widget in dashboard header
  * RAM usage widget in dashboard header
  * Dynamic updates via WebSocket

* **Discord Integration**: Enhanced webhook system with Discord support:
  * Native Discord message formatting
  * Customizable bot name and avatar
  * Rich message content with UPS status information

* **Data Export**: Added JSON export functionality:
  * Download complete UPS data in JSON format
  * Accessible from options page
  * Includes all UPS variables and measurements
  * Useful for diagnostics and data analysis

* **Connection Management**: Improved UPS connection reliability:
  * Added connection checker with automatic polling recovery
  * Better handling of intermittent connection issues
  * Intelligent reconnection attempts with backoff strategy
  * Enhanced error reporting for connection failures

* **Configuration Improvements**:
  * Added Initial Setup Variables card in Advanced options
  * Fixed Amazon SES email provider configuration
  * Simplified Docker Compose with mandatory SECRET_KEY for encryption
  * Improved configuration validation and error handling

* **Enhanced UPS Driver Support**:
  * Added support for usbhid-ups
  * Added support for nutdrv_qx
  * Added support for blazer_usb
  * Added support for blazer_ser
  * Added support for snmp-ups
  * Added support for richcomm_usb
  * Added support for tripplite_usb
  * Added support for riello_usb
  * Added support for apcsmart
  * Added support for mge-shut
  * Added support for genericups
  * Added support for iebert
  * Added support for victronups
  * Added support for powercom
  * Added support for clone
  * Added support for upscode2
  * Added support for bestups
  * Added support for belkin
  * Added support for dummy-ups


## Version 0.1.5 (08/04/2025)
  * Fix Mail Provider in Custom mode and Mailgun (Also Fix TLS/STARTTLS)
  * Fix Webhook

## Version 0.1.4 (03/04/2025)
* **Modular Codebase Architecture**: Restructured the entire application into specialized Python modules:
  * Improved code organization with dedicated modules for each feature
  * Enhanced maintainability with clear separation of concerns
  * Simplified future development with standardized module interfaces
  * Optimized import structure to avoid circular dependencies
* **Documentation Updates**:
  * Corrected SNMP UPS configuration guidance to use UPS_PORT instead of UPS_HOST for specifying IP address
  * Special thanks to user @seanpdiaz for identifying this important clarification
* **Pure ORM Implementation**: Complete migration to ORM-based database operations:
  * Replaced all direct SQL queries with SQLAlchemy ORM models
  * Enhanced database integrity with relationship constraints
  * Improved type safety and query performance
  * Added centralized model registry for global access
* **Additional Notification Channels**:
  * **Ntfy Integration**: Added support for Ntfy push notifications:
    * Configurable notification delivery for critical events
    * Support for multiple notification topics
    * Customizable notification priorities and tags
  * **Webhook Support**: Added comprehensive webhook integration:
    * Flexible HTTP callback system for third-party integrations
    * Customizable payload templates for different event types
    * Support for authentication headers and various HTTP methods
    * Detailed delivery status tracking and error handling
  * **Enhanced Email System**: Improved email notification capabilities:
    * Support for multiple email accounts for notification delivery
    * Streamlined email provider configuration with pre-configured settings
    * More flexible recipient management
    * Improved email template customization
* **Advanced Configuration Section**: New dedicated area for advanced settings:
  * NUT configuration management through the web interface
  * Custom polling interval configuration
  * Fine-grained logging controls
  * System diagnostics and troubleshooting tools
* **Modular JavaScript Architecture**: Reorganized frontend code for better maintainability:
  * Split monolithic JavaScript files into specialized modules
  * Created utility libraries for common functions
  * Improved code reuse and organization
  * Enhanced frontend performance with optimized code loading
* **Enhanced Options Interface**:
  * Modular settings sections with improved organization
  * Specialized configuration panels for each feature area
  * Improved validation and error handling
  * Real-time feedback for configuration changes
* **UX/UI Improvements**:
  * Modernized user interface components
  * Enhanced responsive design across all pages
  * Improved accessibility and usability
  * Better visual feedback for user actions
  * Added official Nutify logo and favicon for brand identity
* **Backend Optimizations**:
  * Improved caching strategy for better performance
  * Enhanced error handling and recovery
  * More detailed logging for troubleshooting
  * Optimized database queries for faster response times
* **Improved Event Handling System**:
  * Eliminated direct upsmon.conf queries in favor of native Python integration
  * Streamlined event processing for improved stability and responsiveness
  * Reduced system resource usage with more efficient event tracking
  * Enhanced event detection and notification delivery
* **Real-time Data Optimization**:
  * Implemented WebSocket-based caching for real-time data delivery
  * Significantly reduced CPU and RAM usage by eliminating repetitive upsc calls
  * Improved data refresh rates and consistency across the interface
  * Enhanced user experience with more responsive real-time updates

## Version 0.1.3 (25/03/2025)

* **Enhanced CLIENT Mode Reliability**: Implemented a robust multi-layered detection system for CLIENT mode:
  * Added triple-check system for mode detection (environment variable, flag file, nut.conf)
  * Implemented intelligent driver management to skip local drivers in CLIENT mode
  * Fixed issue with driver startup in CLIENT mode causing permission errors
  * Added detailed debug information for mode detection
* **Improved Service Monitoring**: Enhanced service monitoring in CLIENT mode:
  * Added smart host detection for UPS communication checks
  * Enhanced error recovery for remote UPS connections
  * Implemented graceful handling of driver failures in CLIENT mode
* **Updated Documentation**: Added comprehensive CLIENT mode information to documentation
* **Improved CLIENT Mode Functionality**: Enhanced detection of CLIENT/SERVER mode:
  * Added robust fallback mechanisms for mode detection
  * Fixed issue with driver startup in CLIENT mode
  * Improved error handling when connecting to remote UPS servers
  * Added detailed debug logging for troubleshooting mode configuration
* **Documentation Updates**: Added clearer CLIENT mode setup instructions
* **Error Handling**: Added more comprehensive error messages for improved troubleshooting
* **Operational Modes**: Added operational mode selection with new NUT_TYPE variable:
  * SERVER mode (default): Run full NUT server with local UPS drivers
  * CLIENT mode: Connect to remote NUT server, no local drivers
* **Dynamic Configuration**: Implemented automatic configuration based on selected mode:
  * Dynamic nut.conf generation with appropriate MODE setting
  * Automatic driver management based on operational mode
  * Smart detection and handling of remote UPS connections
* **Flag File Mechanism**: Added flag file mechanism to indicate client mode to all scripts
* **Documentation**: Enhanced documentation with detailed explanations of both modes
* **User Experience**: Improved user experience with clearer configuration options
* **Extended UPS Driver Support**: Added explicit support for nutdrv_qx driver for Megatec/Q1 protocol UPS devices.
* **Improved UPS Compatibility**: Enhanced compatibility with a wider range of UPS models through additional driver options.
* **Updated Documentation**: Added comprehensive documentation on supported UPS drivers and their use cases.
* **Driver Selection Guide**: Added guidance on selecting the appropriate driver for different UPS models.

## Version 0.1.2 (08/03/2025)

* **International Time Format Support**: Added robust time parsing to support various international time formats including AM/PM notation.
* **Enhanced Startup Summary**: Added a clear service summary at container startup showing configuration status, UPS service status, and web interface access URL.
* **Improved Default Values**: Added sensible default values for all configuration parameters in docker-compose.yaml with clear documentation.
* **Simplified UPS Authentication**: UPSCMD_USER and UPSCMD_PASSWORD now automatically use UPS_USER and UPS_PASSWORD values if not specified.
* **Required Parameters Highlighting**: Clearly marked required parameters like ENCRYPTION_KEY in the configuration.
* **Improved Documentation**: Enhanced comments in docker-compose.yaml for better user experience.


## Version 0.1.1 (08/03/2025)

* **Automatic Database Management**: Added automatic check and fix for SQLite database permissions to prevent read-only database errors.
* **Improved Error Handling**: Enhanced templates to handle missing data correctly with existence checks for all fields.
* **UPS Compatibility**: Improved support for UPS devices that don't provide all standard data fields.
* **Security Enhancements**: Modified Dockerfile to add the nut user to necessary groups (plugdev, dialout, input, usb) for proper device access.
* **Fallback Mechanism**: Added dummy UPS configuration for testing or when no physical UPS is detected.
* **Remote Monitoring**: Added netclient support for remote UPS monitoring.
* **SSL Support**: Added automatic SSL certificate generation and management for secure HTTPS connections.
* **Improved Logging**: Enabled startup and debug logging by default for better troubleshooting.
* **Build Fixes**: Fixed Dockerfile to properly create SSL directory instead of copying from non-existent source.
* **Dummy UPS Control**: Fixed dummy UPS fallback to only activate when explicitly enabled.
* **Robust SSL Implementation**: Added gunicorn with eventlet worker for production-grade SSL support.

## Version 0.1.0 (07/03/2025)

* Added automatic check and fix for SQLite database permissions
* Improved templates to handle missing data correctly
* Added existence checks for all fields in templates (battery.html, power.html, energy.html, header.html)
* Fixed "sqlite3.OperationalError: attempt to write a readonly database" error
* Enhanced error handling for UPS devices that don't provide all standard data
* Modified Dockerfile to add nut user to necessary groups (plugdev, dialout, input, usb)
* Added dummy UPS configuration file for fallback when no physical UPS is detected
* Enabled startup and debug logging by default
* Added netclient for remote UPS monitoring
* Simplified UPS verification method

## Version 0.0.1 (05/03/2025)

* First version of Nutify 
