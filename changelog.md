# Nutify Changelog

## Unreleased

<!-- Add verified release notes here before preparing a new version. -->

## Version 0.3.0 (Public Testing, 23/08/2026)

### NUT, targets, and hardware

* Fixed Wizard validation accepting the transient NUT `WAIT` state as success. Single, Multi, local, remote, and mixed final tests now wait for a ready `ups.status`; nominal-power prompts use structured live data and no longer report `ups.realpower.nominal` as missing before driver initialization completes.
* Updated Network UPS Tools to `2.8.5`, including the upstream Arduino HID mappings used by devices such as the UGREEN US3000.
* Added Raspberry Pi 3 support through a dedicated `linux/arm/v7` image tag for 32-bit operating systems. Pi 3 and Pi 4 ARMv7 images share the same compatible build. ([#147](https://github.com/DartSteven/Nutify/issues/147))
* Added complete SNMPv3 setup support, including security level, username, authentication protocol/password, and privacy protocol/password. Network drivers require an explicit UPS hostname or IP address in `port`; the wizard separates the UPS endpoint from the local NUT server, rejects `auto` for SNMP, and blocks invalid preview, test, and save requests. Docker always activates Linux NUT paths while direct macOS development keeps Homebrew paths. ([#157](https://github.com/DartSteven/Nutify/issues/157))
* Fixed target editing when nominal power is unset and moved Test/Save feedback into the target editor. ([#151](https://github.com/DartSteven/Nutify/issues/151))
* Polling interval and metadata changes no longer require a new connection test unless connection identity changed. ([#152](https://github.com/DartSteven/Nutify/issues/152))

### Events and notifications

* Fixed notification settings routes so explicit `target_id` selection is honored consistently by retrieval, single-event updates, batch updates, and email-config lookups. Single-profile dispatch continues to use canonical global scope. ([#166](https://github.com/DartSteven/Nutify/pull/166))
* Added target-scoped script actions for UPS events and battery thresholds. Conditions are evaluated after every successful poll, execute once while active, rearm after recovery, run outside the polling thread, use a bounded timeout, and do not inherit application secrets. ([#137](https://github.com/DartSteven/Nutify/issues/137))
* Fixed single-profile notification dispatch so Event Matrix routes work without switching to Multi Monitor.
* Made `ups_opt_notification` the only Event Matrix routing source. Webhook provider records now contain transport settings only, preventing duplicate/conflicting webhook configuration. ([#136](https://github.com/DartSteven/Nutify/issues/136))
* Fixed saved webhook tests and real event dispatch with encrypted Bearer tokens while keeping API responses masked. ([#154](https://github.com/DartSteven/Nutify/issues/154), [#162](https://github.com/DartSteven/Nutify/issues/162))
* Added auth-less SMTP relay support. Blank username/password now emit `auth off`; sender address is independent from username; incomplete credential pairs fail closed. No-auth configs remain visible in provider, Event Matrix, and report selectors. ([#141](https://github.com/DartSteven/Nutify/issues/141), [#164](https://github.com/DartSteven/Nutify/issues/164))
* Fixed missing target-aware mail routing rows, stable event subjects, UTF-8 multipart MIME output, and duplicate `MIME-Version` headers. ([#132](https://github.com/DartSteven/Nutify/issues/132))
* Added one canonical notification card shared by Mail, Ntfy, Telegram, and Webhook. Target metrics and separate Input/Output values now render consistently in text and graphic modes. ([#129](https://github.com/DartSteven/Nutify/issues/129))
* Fixed event callback argument-order handling and added live-state validation for direct NUT power callbacks.
* Added per-target communication-failure debounce and duplicate-event suppression. A transient query failure no longer creates false `COMMBAD`, `COMMOK`, `ONBATT`, or `LOWBATT` events, and low-charge fallback applies only while NUT explicitly reports battery operation. ([#158](https://github.com/DartSteven/Nutify/issues/158), [#159](https://github.com/DartSteven/Nutify/issues/159))

### Interface and appearance

* Added an appearance controller with independent interface skin (`Classic` or opt-in `Next`) and color mode (`Light` or `Dark`). Classic remains the default, Next styles remain isolated, hero surfaces use dedicated Light/Dark contrast tokens, and login controls retain correct contrast on the light login surface.
* Kept the first-run Wizard permanently on its original Classic Light surface. Saved dashboard skin/theme preferences are temporarily isolated during setup and restored when leaving it, preventing dark cards, labels, and inputs from leaking into the Wizard.

### Authentication and deployment

* Added secure generic OpenID Connect SSO using Authorization Code flow with PKCE S256, state, nonce, exact issuer validation, matching ID-token/UserInfo subjects, explicit group authorization, and immutable `issuer + subject` identity binding. Username/email collisions fail closed; OIDC-only accounts cannot gain local passwords or local role overrides; local administrator login remains available. ([#167](https://github.com/DartSteven/Nutify/pull/167))
* Added **System -> Authentication**, where administrators can configure database-managed OIDC, validate discovery/JWKS, test the complete browser flow, and enable SSO without editing `.env`. Secrets are encrypted and masked; activation is blocked until verification succeeds.
* Added a dual-method login chooser, emergency `/auth/login?local=1` access, masked read-only environment mode, and optional provider-advertised Dynamic Client Registration without persisting its one-time access token.
* Added fully documented Compose profiles: a simple secure default with local login and guided SSO, plus a separate fail-closed `docker-compose.oidc.yaml` override for environment-managed OIDC deployments.
* Preserved Raspberry Pi 3/4 ARMv7 builds by adding the `libffi` build/runtime dependencies required by the OIDC cryptography stack. A complete ARMv7 Docker image build and runtime smoke test passed.
* Restored USB HID discovery and driver access in the secure base Compose profile without restoring privileged mode or the complete host `/dev` tree. Access is limited to Linux USB character devices (major 189), udev metadata is read-only, runtime USB groups are detected dynamically, and host device ownership/modes are never changed. The hardware override remains only for stable serial or non-USB paths.
* Added a verified release pipeline with backend, frontend lint/build, and Compose checks; immutable version tags; atomic `main` + tag publication; GitHub Releases; deployment bundles; SHA-256 checksums; Docker image manifests; resumable interrupted releases; and CI for every push and pull request. Public Testing and Release Candidate builds are published as GitHub pre-releases; Stable builds become the latest release.
* Updated vulnerable frontend transitive dependencies and added a high/critical npm audit release gate. User-controlled target names and locations are HTML-escaped before ECharts globe/map tooltip rendering.
* Added rate-limited admin password recovery using the runtime `SECRET_KEY`; recovery remains restricted to administrator accounts. ([#135](https://github.com/DartSteven/Nutify/issues/135))
* Replaced the default privileged Compose configuration with a least-privilege profile: no complete host `/dev`, `SYS_ADMIN`, `SYS_RAWIO`, or `MKNOD`. USB HID access is constrained to Linux USB major 189; direct serial hardware is available through the explicit `docker-compose.hardware.yaml` override, independently from Single/Multi monitoring profile selection. ([#156](https://github.com/DartSteven/Nutify/issues/156))
* Required `SECRET_KEY` through an ignored `.env`, removed secret fragments from startup logging, and excluded runtime databases, logs, and generated configuration from Docker build context.
* Renamed the user-facing Werkzeug logging option to `HTTP Access Logs`. ([#149](https://github.com/DartSteven/Nutify/issues/149))

### Reports, charts, and performance

* Fixed runaway browser CPU and memory usage caused by a single-profile topbar render loop. Realtime charts keep smooth 24 FPS scrolling while avoiding nested redraws, limiting canvas resolution, matching data refresh to the polling interval, and pausing continuous rendering in hidden tabs.
* Added rolling `Last 7 Days`, `Last 30 Days`, and `Last 12 Months` presets to dashboard charts, manual reports, and scheduled reports. Multi-day axes and CSV exports retain date and time. ([#133](https://github.com/DartSteven/Nutify/issues/133))
* Fixed long-range Energy performance by using materialized rollups and refreshing current hour/day/month/year parents whenever a minute is stored. ([#150](https://github.com/DartSteven/Nutify/issues/150), [#159](https://github.com/DartSteven/Nutify/issues/159))
* Added dynamic discovery and historical graphing for arbitrary `outlet*.realpower` NUT variables. ([#145](https://github.com/DartSteven/Nutify/issues/145))
* Fixed chart legends, labels, axes, and titles in light mode with shared live theme colors. ([#134](https://github.com/DartSteven/Nutify/issues/134))
* Added authenticated HTTP snapshot fallback for topbar telemetry when Socket.IO is unavailable through a reverse proxy. Additional exact origins can be configured with `SOCKETIO_ALLOWED_ORIGINS`; wildcards are rejected. ([#129](https://github.com/DartSteven/Nutify/issues/129))

## Version 0.2.2 (29/04/2026)

* Updated NUT to 2.8.5.
* Fixed Ntfy notifications, SMTP blank credentials, webhooks, mail notification settings, and light-mode chart text.
* Added event script execution, administrator password recovery, and report date presets.

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
