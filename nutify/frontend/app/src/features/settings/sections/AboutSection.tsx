/**
 * Aboutsection.
 *
 * Frontend module used by Nutify React UI flows and state management.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { getAboutImage, getSystemInfo } from '../../../lib/api/settings'

type SystemInfo = {
  version: string
  lastUpdate: string
  status: string
  changelog: string
}

function parseSystemInfo(payload: unknown): SystemInfo {
  if (!payload || typeof payload !== 'object') {
    return {
      version: '0.0.1',
      lastUpdate: 'Unknown',
      status: 'Unknown',
      changelog: 'No changelog available.',
    }
  }

  const root = payload as Record<string, unknown>
  const data = root.data && typeof root.data === 'object' ? (root.data as Record<string, unknown>) : root

  return {
    version: String(data.version ?? '0.0.1'),
    lastUpdate: String(data.last_update ?? data.lastUpdate ?? 'Unknown'),
    status: String(data.status ?? 'Unknown'),
    changelog: String(data.changelog ?? 'No changelog available.'),
  }
}

function parseAboutImage(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') {
    return null
  }

  const row = payload as Record<string, unknown>
  const candidate = row.data
  if (typeof candidate !== 'string' || !candidate.trim()) {
    return null
  }

  return candidate
}

export function AboutSection() {
  const infoQuery = useQuery({
    queryKey: ['settings', 'about', 'system-info'],
    queryFn: getSystemInfo,
  })

  const imageQuery = useQuery({
    queryKey: ['settings', 'about', 'image'],
    queryFn: getAboutImage,
    retry: false,
  })

  const info = useMemo(() => parseSystemInfo(infoQuery.data), [infoQuery.data])
  const aboutImage = useMemo(() => parseAboutImage(imageQuery.data), [imageQuery.data])

  const [showAuthorImage, setShowAuthorImage] = useState(false)
  const [imageError, setImageError] = useState(false)
  const [isChangelogExpanded, setIsChangelogExpanded] = useState(false)
  const [isLicenseExpanded, setIsLicenseExpanded] = useState(false)
  const [isLicenseVisible, setIsLicenseVisible] = useState(false)
  const [licenseMaxHeight, setLicenseMaxHeight] = useState('0')
  const [licenseOpacity, setLicenseOpacity] = useState('0')

  const authorHoverTimerRef = useRef<number | null>(null)
  const licenseHideTimerRef = useRef<number | null>(null)
  const licenseContentRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    setImageError(false)
  }, [aboutImage])

  useEffect(() => {
    return () => {
      if (authorHoverTimerRef.current !== null) {
        window.clearTimeout(authorHoverTimerRef.current)
      }
      if (licenseHideTimerRef.current !== null) {
        window.clearTimeout(licenseHideTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (licenseHideTimerRef.current !== null) {
      window.clearTimeout(licenseHideTimerRef.current)
      licenseHideTimerRef.current = null
    }

    if (isLicenseExpanded) {
      setIsLicenseVisible(true)
      window.requestAnimationFrame(() => {
        const contentHeight = licenseContentRef.current?.scrollHeight ?? 0
        setLicenseMaxHeight(`${contentHeight}px`)
        setLicenseOpacity('1')
      })
      return
    }

    setLicenseMaxHeight('0')
    setLicenseOpacity('0')
    licenseHideTimerRef.current = window.setTimeout(() => {
      setIsLicenseVisible(false)
    }, 300)
  }, [isLicenseExpanded])

  const handleAuthorMouseEnter = () => {
    if (authorHoverTimerRef.current !== null) {
      window.clearTimeout(authorHoverTimerRef.current)
    }

    authorHoverTimerRef.current = window.setTimeout(() => {
      setShowAuthorImage(true)
    }, 5000)
  }

  const handleAuthorMouseLeave = () => {
    if (authorHoverTimerRef.current !== null) {
      window.clearTimeout(authorHoverTimerRef.current)
      authorHoverTimerRef.current = null
    }
    setShowAuthorImage(false)
  }

  const statusClassName = useMemo(() => {
    const baseClass = 'version-value'
    const normalized = info.status.trim().toLowerCase()
    if (!normalized) {
      return baseClass
    }
    return `${baseClass} version-${normalized.replace(/\s+/g, '-')}`
  }, [info.status])

  const canShowAuthorImage = Boolean(aboutImage) && !imageError && showAuthorImage

  return (
    <>
      <div className="page_header">
        <div className="page_title">
          <p className="page_subtitle">Nutify Advanced UPS monitoring and energy management solution</p>
        </div>
        <div className="page_actions">
          <a href="https://github.com/DartSteven/nutify" target="_blank" rel="noreferrer" className="contact-link">
            <i className="fab fa-github" />
            <span>Star on GitHub</span>
          </a>
        </div>
      </div>

      <div className="mt-6 about-top-grid">
        <div className="combined_card">
          <div className="card_header">
            <h2>Project Status</h2>
          </div>
          <div style={{ padding: '0.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Current Release</span>
              <span id="projectVersion">{info.version}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Last Update</span>
              <span id="lastUpdate">{info.lastUpdate}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Status</span>
              <span id="projectStatus" className={statusClassName}>{info.status}</span>
            </div>
          </div>
        </div>

        <div className="combined_card" style={{ minHeight: '280px', height: 'auto' }}>
          <div className="combined_header">
            <h2>Author</h2>
          </div>

          <div className="about-author-layout">
            <div className="about-author-avatar-wrap">
              <div
                id="authorIcon"
                className={`author-icon ${canShowAuthorImage ? 'show-image' : ''}`}
                onMouseEnter={handleAuthorMouseEnter}
                onMouseLeave={handleAuthorMouseLeave}
              >
                <div className="icon-container">
                  <i className="fas fa-user-circle" />
                </div>
                <div className="image-container">
                  <img
                    id="authorImage"
                    src={!imageError && aboutImage ? aboutImage : ''}
                    alt="Author"
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    onError={() => setImageError(true)}
                  />
                </div>
              </div>
            </div>

            <div className="about-author-content">
              <div>
                <p style={{ lineHeight: 1.6, marginBottom: '1rem' }}>
                  Hi, I&apos;m <strong>Dart Steven</strong>, a technology enthusiast and self-taught developer with a passion for open-source solutions. I created Nutify to address the need for efficient UPS monitoring while exploring modern technologies. The project&apos;s name combines NUT (Network UPS Tools) with notifications, reflecting its core purpose: providing real-time device status updates through a modern interface.
                </p>
                <p style={{ lineHeight: 1.6, marginBottom: '1.5rem' }}>
                  My journey in software development has been driven by curiosity and hands-on learning. Through experimenting with Python, JavaScript, and web technologies, I&apos;ve focused on creating solutions that are both powerful and user-friendly. Nutify represents this philosophy, combining robust monitoring capabilities with an intuitive interface.
                </p>
              </div>

              <div className="about-contact-grid">
                <a href="https://github.com/DartSteven" target="_blank" rel="noreferrer" className="contact-link" style={{ flex: 1, justifyContent: 'center' }}>
                  <i className="fab fa-github" />
                  <span>GitHub</span>
                </a>
                <a href="mailto:dartsteven@icloud.com" className="contact-link" style={{ flex: 1, justifyContent: 'center' }}>
                  <i className="fas fa-envelope" />
                  <span>Email</span>
                </a>
                <a href="https://buymeacoffee.com/dartsteven" target="_blank" rel="noreferrer" className="contact-link" style={{ flex: 1, justifyContent: 'center' }}>
                  <i className="fas fa-coffee" />
                  <span>Buy me a coffee</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="combined_card mt-6" style={{ minHeight: 'auto' }}>
        <div
          className="combined_header"
          style={{ cursor: 'pointer' }}
          id="changelogTrigger"
          onClick={() => setIsChangelogExpanded((current) => !current)}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
            <h2>Changelog</h2>
            <i className={`fas fa-chevron-down license-chevron ${isChangelogExpanded ? 'expanded' : ''}`} style={{ transition: 'transform 0.3s ease' }} />
          </div>
        </div>
        <div
          id="changelogContent"
          style={{
            display: 'block',
            transition: 'max-height 0.3s ease, opacity 0.3s ease, padding 0.3s ease',
            maxHeight: isChangelogExpanded ? '420px' : '0',
            opacity: isChangelogExpanded ? '1' : '0',
            overflow: 'hidden',
            padding: isChangelogExpanded ? '0.5rem' : '0',
          }}
        >
          <div className="card_header" style={{ padding: isChangelogExpanded ? undefined : 0 }}>
            <p className="card_subtitle">Recent project updates and release notes.</p>
          </div>
          <div className="changelog-content about-changelog-scroll">
            <pre
              id="changelogText"
              className="changelog-text"
              style={{
                margin: 0,
                fontSize: '0.95rem',
                lineHeight: 1.5,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {info.changelog}
            </pre>
          </div>
        </div>
      </div>

      <div className="combined_card mt-6" style={{ minHeight: 'auto' }}>
        <div
          className="combined_header"
          style={{ cursor: 'pointer' }}
          id="licenseTrigger"
          onClick={() => setIsLicenseExpanded((current) => !current)}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
            <h2>License</h2>
            <i className={`fas fa-chevron-down license-chevron ${isLicenseExpanded ? 'expanded' : ''}`} style={{ transition: 'transform 0.3s ease' }} />
          </div>
        </div>

        <div
          id="licenseContent"
          ref={licenseContentRef}
          className={`license-content ${isLicenseExpanded ? 'expanded' : ''}`}
          style={{
            display: isLicenseVisible ? 'block' : 'none',
            transition: 'all 0.3s ease',
            maxHeight: licenseMaxHeight,
            opacity: licenseOpacity,
            overflow: 'hidden',
          }}
        >
          <div style={{ display: 'flex', gap: '2rem', padding: '1rem 0' }}>
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'flex-start', flex: '0 0 200px', paddingTop: '1rem' }}>
              <div style={{ width: '180px', height: '180px', background: 'var(--bg-secondary)', borderRadius: '50%', display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative', boxShadow: '0 0 20px rgba(37, 99, 235, 0.1)' }}>
                <div style={{ position: 'absolute', width: '100%', height: '100%', borderRadius: '50%', border: '3px solid var(--primary-color)', opacity: 0.2 }} />
                <div style={{ position: 'absolute', width: 'calc(100% - 10px)', height: 'calc(100% - 10px)', borderRadius: '50%', border: '2px solid var(--primary-color)', opacity: 0.3 }} />
                <i className="fas fa-balance-scale" style={{ fontSize: '7rem', color: 'var(--primary-color)', filter: 'drop-shadow(0 4px 6px rgba(37, 99, 235, 0.2))' }} />
              </div>
            </div>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div>
                <h3 style={{ fontSize: '1.1rem', color: 'var(--text-primary)', marginBottom: '0.75rem' }}>Usage License – Customized Version Based on MIT</h3>
                <p style={{ lineHeight: 1.6, color: 'var(--text-secondary)' }}>
                  This software is released under a modified license for personal and non-commercial use. The license is designed to protect both users&apos; freedom to use the software and the author&apos;s rights.
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div style={{ background: 'var(--bg-secondary)', padding: '1.25rem', borderRadius: '0.5rem' }}>
                  <h4 style={{ fontSize: '0.9rem', color: 'var(--text-primary)', marginBottom: '1rem' }}>Permitted Uses</h4>
                  <ul style={{ listStyleType: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    <li style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
                      <i className="fas fa-check" style={{ color: 'var(--primary-color)', width: '20px', marginTop: '3px' }} />
                      <span>The use, copying, and modification of the software are permitted solely for personal and non-commercial purposes.</span>
                    </li>
                    <li style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
                      <i className="fas fa-check" style={{ color: 'var(--primary-color)', width: '20px', marginTop: '3px' }} />
                      <span>Any authorized use must include attribution to the original author.</span>
                    </li>
                  </ul>
                </div>

                <div style={{ background: 'var(--bg-secondary)', padding: '1.25rem', borderRadius: '0.5rem' }}>
                  <h4 style={{ fontSize: '0.9rem', color: 'var(--text-primary)', marginBottom: '1rem' }}>Restrictions</h4>
                  <ul style={{ listStyleType: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    <li style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
                      <i className="fas fa-times" style={{ color: '#ef4444', width: '20px', marginTop: '3px' }} />
                      <span>Any commercial use requires written permission from the author.</span>
                    </li>
                    <li style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
                      <i className="fas fa-times" style={{ color: '#ef4444', width: '20px', marginTop: '3px' }} />
                      <span>Unauthorized redistribution of both the original software and modified versions is not allowed.</span>
                    </li>
                  </ul>
                </div>
              </div>

              <div style={{ background: 'var(--bg-secondary)', padding: '1.25rem', borderRadius: '0.5rem' }}>
                <h4 style={{ fontSize: '0.9rem', color: 'var(--text-primary)', marginBottom: '1rem' }}>Important Notice</h4>
                <p style={{ lineHeight: 1.6, color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                  The software is provided &quot;as is,&quot; without any warranties of any kind, either express or implied. This includes but is not limited to warranties of merchantability, fitness for a particular purpose, and non-infringement.
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border-color)' }}>
                <div style={{ flex: 1, color: 'var(--text-secondary)' }}>
                  <i className="fas fa-info-circle" />
                  {' '}
                  For requests regarding usage, modifications, or distribution:
                </div>
                <a href="mailto:dartsteven@icloud.com" className="contact-link">
                  <i className="fas fa-envelope" />
                  <span>Contact Author</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
