/**
 * Commandcatalog.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

export type CommandDetail = {
  title: string
  description: string
  warning: string
}

export const COMMAND_ICONS: Record<string, string> = {
  'beeper.enable': 'fa-volume-up',
  'beeper.disable': 'fa-volume-mute',
  'beeper.toggle': 'fa-volume-down',
  'beeper.mute': 'fa-volume-mute',
  'beeper.off': 'fa-volume-mute',
  'beeper.on': 'fa-volume-up',
  'test.battery.start': 'fa-play',
  'test.battery.stop': 'fa-stop',
  'test.battery.start.deep': 'fa-car-battery',
  'test.battery.start.quick': 'fa-bolt',
  'test.panel.start': 'fa-tv',
  'test.panel.stop': 'fa-tv',
  'shutdown.return': 'fa-power-off',
  'shutdown.stayoff': 'fa-plug',
  'shutdown.stop': 'fa-stop-circle',
  'shutdown.reboot': 'fa-sync',
  'shutdown.reboot.graceful': 'fa-redo',
  'load.off': 'fa-toggle-off',
  'load.on': 'fa-toggle-on',
  'load.off.delay': 'fa-clock',
  'load.on.delay': 'fa-clock',
  'outlet.1.load.off': 'fa-plug',
  'outlet.1.load.on': 'fa-plug',
  'outlet.2.load.off': 'fa-plug',
  'outlet.2.load.on': 'fa-plug',
  'calibrate.start': 'fa-chart-line',
  'calibrate.stop': 'fa-stop',
  'reset.input.minmax': 'fa-undo',
  'reset.watchdog': 'fa-sync',
  'bypass.start': 'fa-random',
  'bypass.stop': 'fa-random',
}

export const COMMAND_DETAILS: Record<string, CommandDetail> = {
  'beeper.disable': {
    title: 'Disable Beeper',
    description: 'Permanently disables the UPS beeper.',
    warning: 'The beeper will remain disabled until manually re-enabled.',
  },
  'beeper.enable': {
    title: 'Enable Beeper',
    description: 'Enables the UPS beeper.',
    warning: 'Restores the normal beeper functionality.',
  },
  'beeper.toggle': {
    title: 'Toggle Beeper',
    description: 'Toggles the UPS beeper between active and inactive.',
    warning: 'Alternates the beeper status between active and inactive.',
  },
  'beeper.mute': {
    title: 'Mute Beeper',
    description: 'Silences the UPS beeper temporarily.',
    warning: 'The beeper may automatically reactivate in case of new events.',
  },
  'load.off': {
    title: 'Immediate Shutdown',
    description: 'Turns off the power to all connected devices immediately.',
    warning: 'ATTENTION: Immediate power interruption! May cause data loss.',
  },
  'load.on': {
    title: 'Immediate Power On',
    description: 'Restores the power to all connected devices immediately.',
    warning: 'Verify that the devices can be safely powered on.',
  },
  'load.off.delay': {
    title: 'Delayed Shutdown',
    description: 'Turns off the power to all connected devices after a configured delay.',
    warning: 'The power will be interrupted at the end of the configured delay.',
  },
  'load.on.delay': {
    title: 'Delayed Power On',
    description: 'Restores the power to all connected devices after a configured delay.',
    warning: 'The power will be restored at the end of the configured delay.',
  },
  'outlet.1.load.off': {
    title: 'Turn Off Outlet 1',
    description: 'Turns off the power to outlet 1.',
    warning: 'Interrupts the power only to the specified outlet.',
  },
  'outlet.1.load.on': {
    title: 'Turn On Outlet 1',
    description: 'Turns on the power to outlet 1.',
    warning: 'Restores the power only to the specified outlet.',
  },
  'outlet.2.load.off': {
    title: 'Turn Off Outlet 2',
    description: 'Turns off the power to outlet 2.',
    warning: 'Interrupts the power only to the specified outlet.',
  },
  'outlet.2.load.on': {
    title: 'Turn On Outlet 2',
    description: 'Turns on the power to outlet 2.',
    warning: 'Restores the power only to the specified outlet.',
  },
  'shutdown.return': {
    title: 'Shutdown with Return',
    description: 'Turns off the UPS and reactivates when the network power returns.',
    warning: 'The systems will automatically restart when the power returns.',
  },
  'shutdown.stayoff': {
    title: 'Shutdown with Return',
    description: 'Turns off the UPS and reactivates when the network power returns.',
    warning: 'The systems will automatically restart when the power returns.',
  },
  'shutdown.stop': {
    title: 'Stop Shutdown',
    description: 'Cancels a shutdown in progress.',
    warning: 'Ensure the interruption is safe for the connected systems.',
  },
  'shutdown.reboot': {
    title: 'Full Reboot',
    description: 'Performs a complete cycle of shutdown and restart.',
    warning: 'All connected systems will be restarted.',
  },
  'shutdown.reboot.graceful': {
    title: 'Graceful Reboot',
    description: 'Performs a controlled restart with a shutdown of the systems.',
    warning: 'Waits for the correct shutdown of the systems before the restart.',
  },
  'test.battery.start': {
    title: 'Standard Battery Test',
    description: 'Starts a complete battery test.',
    warning: 'The test may take several minutes.',
  },
  'test.battery.start.deep': {
    title: 'Deep Battery Test',
    description: 'Performs a deep battery test with a complete discharge/charge cycle.',
    warning: 'ATTENTION: Long test that significantly discharges the battery!',
  },
  'test.battery.start.quick': {
    title: 'Quick Battery Test',
    description: 'Performs a quick battery test.',
    warning: 'Basic test for routine checks.',
  },
  'test.battery.stop': {
    title: 'Stop Battery Test',
    description: 'Stops any ongoing battery test.',
    warning: 'The interruption will provide incomplete results.',
  },
  'calibrate.start': {
    title: 'Start Calibration',
    description: 'Starts the calibration procedure.',
    warning: 'The calibration requires a complete discharge cycle.',
  },
  'calibrate.stop': {
    title: 'Stop Calibration',
    description: 'Stops the ongoing calibration procedure.',
    warning: 'The interruption will invalidate the calibration.',
  },
  'reset.input.minmax': {
    title: 'Reset Input Min/Max',
    description: 'Resets the recorded minimum and maximum values for the input.',
    warning: 'The historical data of the extreme values will be deleted.',
  },
  'reset.watchdog': {
    title: 'Reset Watchdog',
    description: 'Resets the watchdog timer of the UPS.',
    warning: 'May affect automatic monitoring functions.',
  },
  'bypass.start': {
    title: 'Activate Bypass',
    description: 'Activates the bypass mode of the UPS.',
    warning: 'The power will pass directly from the network to the devices.',
  },
  'bypass.stop': {
    title: 'Deactivate Bypass',
    description: 'Deactivates the bypass mode of the UPS.',
    warning: 'The power will return to pass through the UPS.',
  },
}
