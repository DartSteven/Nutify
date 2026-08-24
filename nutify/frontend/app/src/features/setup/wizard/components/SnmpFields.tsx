type SnmpFieldsProps = {
  containerId: string
  idPrefix?: string
}

export function SnmpFields({ containerId, idPrefix = '' }: SnmpFieldsProps) {
  const id = (name: string) => `${idPrefix}snmp_${name}`

  return (
    <div id={containerId} className="wizard-snmp-fields hidden">
      <div className="form-grid-2">
        <div className="form-group">
          <label htmlFor={id('version')}>SNMP Version:</label>
          <select id={id('version')} defaultValue="v1">
            <option value="v1">v1</option>
            <option value="v2c">v2c</option>
            <option value="v3">v3</option>
          </select>
        </div>
        <div id={`${idPrefix}snmp_community_group`} className="form-group">
          <label htmlFor={id('community')}>SNMP Community:</label>
          <input type="password" id={id('community')} defaultValue="public" autoComplete="off" />
          <div className="form-help">Required for SNMP v1 and v2c.</div>
        </div>
      </div>

      <div id={`${idPrefix}snmp_v3_identity`} className="form-grid-2 hidden">
        <div className="form-group">
          <label htmlFor={id('sec_level')}>SNMPv3 Security Level:</label>
          <select id={id('sec_level')} defaultValue="authPriv">
            <option value="noAuthNoPriv">No authentication, no privacy</option>
            <option value="authNoPriv">Authentication, no privacy</option>
            <option value="authPriv">Authentication and privacy</option>
          </select>
        </div>
        <div className="form-group">
          <label htmlFor={id('sec_name')}>SNMPv3 Security Name:</label>
          <input type="text" id={id('sec_name')} autoComplete="off" />
        </div>
      </div>

      <div id={`${idPrefix}snmp_v3_auth`} className="form-grid-2 hidden">
        <div className="form-group">
          <label htmlFor={id('auth_protocol')}>Authentication Protocol:</label>
          <select id={id('auth_protocol')} defaultValue="SHA">
            <option value="MD5">MD5</option>
            <option value="SHA">SHA</option>
            <option value="SHA256">SHA256</option>
            <option value="SHA384">SHA384</option>
            <option value="SHA512">SHA512</option>
          </select>
        </div>
        <div className="form-group">
          <label htmlFor={id('auth_password')}>Authentication Password:</label>
          <input type="password" id={id('auth_password')} autoComplete="new-password" />
        </div>
      </div>

      <div id={`${idPrefix}snmp_v3_privacy`} className="form-grid-2 hidden">
        <div className="form-group">
          <label htmlFor={id('priv_protocol')}>Privacy Protocol:</label>
          <select id={id('priv_protocol')} defaultValue="AES">
            <option value="DES">DES</option>
            <option value="AES">AES</option>
            <option value="AES192">AES192</option>
            <option value="AES256">AES256</option>
          </select>
        </div>
        <div className="form-group">
          <label htmlFor={id('priv_password')}>Privacy Password:</label>
          <input type="password" id={id('priv_password')} autoComplete="new-password" />
        </div>
      </div>

      <div className="form-group">
        <label htmlFor={id('mibs')}>MIB Mapping (optional):</label>
        <input type="text" id={id('mibs')} placeholder="auto, apcc, ietf, ..." />
        <div className="form-help">Leave blank for automatic detection.</div>
      </div>
    </div>
  )
}
