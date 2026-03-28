/**
 * Advancedscriptinfomodal.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import type { MultiNutTarget } from '../../../../lib/api/multiNut'

type AdvancedScriptInfoModalProps = {
  target: MultiNutTarget
  onClose: () => void
}

export function AdvancedScriptInfoModal({ target, onClose }: AdvancedScriptInfoModalProps) {
  return (
    <div
      className="modal"
      style={{ display: 'block' }}
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <div className="modal-content options_card">
        <div className="modal-header">
          <h5 className="modal-title">Generated Script Info</h5>
          <button type="button" className="modal-close" onClick={onClose}>
            <i className="fas fa-times" />
          </button>
        </div>

        <div className="modal-body">
          <p>
            <strong>Generate Script</strong> creates a target-scoped <code>NOTIFYCMD</code> bridge for this UPS.
            Use it when this target is monitored by a <strong>remote vanilla NUT host</strong> and you want that host to
            forward <code>upsmon</code> events to this Nutify server.
          </p>

          <p>
            Event flow:
            <br />
            <code>remote upsmon event -&gt; generated NOTIFYCMD script -&gt; Nutify /api/nut_event -&gt; target_id-scoped routing (mail / ntfy / webhook)</code>
          </p>

          <p><strong>Use this when</strong></p>
          <ul>
            <li>The UPS is hosted on another machine that runs standard NUT (not Nutify).</li>
            <li>You need Nutify to receive outage/restore and related <code>upsmon</code> events from that machine.</li>
            <li>You want strict per-target isolation in Multi-UPS routing.</li>
          </ul>

          <p><strong>Setup on the remote NUT host</strong></p>
          <ol>
            <li>
              Copy the generated file to a stable system path:
              <br />
              <code>/etc/nut/nutify_notifycmd_{target.name}.sh</code>
            </li>
            <li>
              Make it executable:
              <br />
              <code>chmod +x /etc/nut/nutify_notifycmd_{target.name}.sh</code>
            </li>
            <li>
              Set it in remote <code>upsmon.conf</code>:
              <br />
              <code>NOTIFYCMD /etc/nut/nutify_notifycmd_{target.name}.sh</code>
            </li>
            <li>Reload or restart the remote NUT monitor service.</li>
          </ol>

          <p>
            <strong>Mandatory:</strong> every event you want to forward must have <code>+EXEC</code> in <code>NOTIFYFLAG</code>.
            Without <code>+EXEC</code>, <code>upsmon</code> will not run <code>NOTIFYCMD</code>.
          </p>

          <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
{`# Keep +EXEC enabled for every forwarded event
NOTIFYFLAG ONLINE   SYSLOG+WALL+EXEC
NOTIFYFLAG ONBATT   SYSLOG+WALL+EXEC
NOTIFYFLAG LOWBATT  SYSLOG+WALL+EXEC
NOTIFYFLAG FSD      SYSLOG+WALL+EXEC
NOTIFYFLAG COMMOK   SYSLOG+WALL+EXEC
NOTIFYFLAG COMMBAD  SYSLOG+WALL+EXEC
NOTIFYFLAG SHUTDOWN SYSLOG+WALL+EXEC
NOTIFYFLAG REPLBATT SYSLOG+WALL+EXEC
NOTIFYFLAG NOCOMM   SYSLOG+WALL+EXEC
NOTIFYFLAG NOPARENT SYSLOG+WALL+EXEC`}
          </pre>

          <p>
            <strong>Security:</strong> the script includes a callback token bound to this target.
            Keep one script per target, do not reuse tokens across targets, and protect file permissions on the remote host.
          </p>

          <p>
            <strong>Destination:</strong> the script variables are editable, but <code>DESTINATION_IP</code> / callback URL must point to
            a Nutify endpoint reachable from that remote host.
          </p>

          <p>
            <strong>Runtime behavior:</strong> the script is non-blocking by design for <code>upsmon</code>.
            On network errors it exits with code <code>0</code> to avoid breaking the NUT event pipeline.
          </p>

          <p>
            <strong>How to verify it works:</strong> in Nutify logs you should see lines like:
            <br />
            <code>NUT event callback received source_ip=... event=... target_id=...</code>
          </p>

          <p>
            Target: <strong>{target.name}</strong> ({target.ups_name}@{target.host})
          </p>
        </div>

        <div className="modal-footer">
          <button
            type="button"
            className="options_btn options_btn_secondary modal-close"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
