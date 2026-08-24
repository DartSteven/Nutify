// @ts-nocheck

const PREFIXES = ['', 'server_', 'multi_target_']

export function registerSnmpRuntime(ctx) {
  function field(prefix, suffix) {
    return document.getElementById(`${prefix}snmp_${suffix}`)
  }

  ctx.actions.readSnmpSettings = function readSnmpSettings(prefix = '') {
    return {
      snmp_version: String(field(prefix, 'version')?.value || 'v1').trim() || 'v1',
      snmp_community: String(field(prefix, 'community')?.value || '').trim(),
      snmp_sec_level: String(field(prefix, 'sec_level')?.value || 'authPriv').trim() || 'authPriv',
      snmp_sec_name: String(field(prefix, 'sec_name')?.value || '').trim(),
      snmp_auth_protocol: String(field(prefix, 'auth_protocol')?.value || 'SHA').trim() || 'SHA',
      snmp_auth_password: String(field(prefix, 'auth_password')?.value || '').trim(),
      snmp_priv_protocol: String(field(prefix, 'priv_protocol')?.value || 'AES').trim() || 'AES',
      snmp_priv_password: String(field(prefix, 'priv_password')?.value || '').trim(),
      snmp_mibs: String(field(prefix, 'mibs')?.value || '').trim(),
    }
  }

  ctx.actions.validateSnmpSettings = function validateSnmpSettings(prefix = '') {
    const settings = ctx.actions.readSnmpSettings(prefix)
    if (settings.snmp_version !== 'v3') {
      return settings.snmp_community ? '' : 'SNMP community is required for SNMP v1 and v2c.'
    }
    if (!settings.snmp_sec_name) return 'SNMPv3 security name is required.'
    if (settings.snmp_sec_level !== 'noAuthNoPriv' && !settings.snmp_auth_password) {
      return 'SNMPv3 authentication password is required.'
    }
    if (settings.snmp_sec_level === 'authPriv' && !settings.snmp_priv_password) {
      return 'SNMPv3 privacy password is required.'
    }
    return ''
  }

  ctx.actions.writeSnmpSettings = function writeSnmpSettings(prefix = '', values = {}) {
    const defaults = {
      version: 'v1', community: 'public', sec_level: 'authPriv', sec_name: '',
      auth_protocol: 'SHA', auth_password: '', priv_protocol: 'AES',
      priv_password: '', mibs: '',
    }
    Object.entries(defaults).forEach(([suffix, fallback]) => {
      const element = field(prefix, suffix)
      if (element) element.value = values[`snmp_${suffix}`] ?? fallback
    })
    ctx.actions.updateSnmpAuthUi(prefix)
  }

  ctx.actions.updateSnmpAuthUi = function updateSnmpAuthUi(prefix = '') {
    const version = String(field(prefix, 'version')?.value || 'v1')
    const level = String(field(prefix, 'sec_level')?.value || 'authPriv')
    document.getElementById(`${prefix}snmp_community_group`)?.classList.toggle('hidden', version === 'v3')
    document.getElementById(`${prefix}snmp_v3_identity`)?.classList.toggle('hidden', version !== 'v3')
    document.getElementById(`${prefix}snmp_v3_auth`)?.classList.toggle(
      'hidden', version !== 'v3' || level === 'noAuthNoPriv',
    )
    document.getElementById(`${prefix}snmp_v3_privacy`)?.classList.toggle(
      'hidden', version !== 'v3' || level !== 'authPriv',
    )
  }

  PREFIXES.forEach((prefix) => {
    field(prefix, 'version')?.addEventListener('change', () => ctx.actions.updateSnmpAuthUi(prefix))
    field(prefix, 'sec_level')?.addEventListener('change', () => ctx.actions.updateSnmpAuthUi(prefix))
    ctx.actions.updateSnmpAuthUi(prefix)
  })
}
