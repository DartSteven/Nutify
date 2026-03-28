/**
 * Command Presentation Helpers.
 *
 * Maps UPS command names to human-friendly metadata and icons.
 */

import { COMMAND_DETAILS, COMMAND_ICONS, type CommandDetail } from './commandCatalog'

function fallbackDetails(commandName: string): CommandDetail {
  return {
    title: commandName,
    description: 'UPS command',
    warning: 'Be careful in executing this command.',
  }
}

export function detailsForCommand(commandName: string): CommandDetail {
  return COMMAND_DETAILS[commandName] ?? fallbackDetails(commandName)
}

export function iconForCommand(commandName: string): string {
  return COMMAND_ICONS[commandName] ?? 'fa-terminal'
}
