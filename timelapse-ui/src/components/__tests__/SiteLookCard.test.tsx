/**
 * Unit Tests for SiteLookCard Component
 *
 * Tests cover:
 * - Render states (disabled, no reference, reference active, error)
 * - Props validation
 * - Mock API responses
 * - User interactions (buttons)
 * - Data display formatting
 * - Camera-specific recommendations
 * - Match quality color coding
 * - Edge cases and error handling
 */

import { render, screen } from '@testing-library/react'
import { SiteLookCard } from '../SiteLookCard'

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  CheckCircle: ({ className }: { className: string }) => <div data-testid="check-circle" className={className} />,
  AlertCircle: ({ className }: { className: string }) => <div data-testid="alert-circle" className={className} />,
  Camera: ({ className }: { className: string }) => <div data-testid="camera-icon" className={className} />,
  Sparkles: ({ className }: { className: string }) => <div data-testid="sparkles-icon" className={className} />,
  Eye: ({ className }: { className: string }) => <div data-testid="eye-icon" className={className} />,
  Target: ({ className }: { className: string }) => <div data-testid="target-icon" className={className} />,
  Info: ({ className }: { className: string }) => <div data-testid="info-icon" className={className} />,
}))

describe('SiteLookCard Component', () => {
  // Helper functions
  const createMockData = (overrides = {}) => ({
    enabled: true,
    has_site_reference: false,
    is_site_reference: false,
    lut_generated: false,
    ...overrides,
  })

  const createReferenceInfo = (overrides = {}) => ({
    site_id: 'construction-site-1',
    created_at: '2026-07-12T12:00:00Z',
    created_by_camera: 'Nikon Z30',
    quality_score: 92.5,
    scene_type: 'day',
    picture_control: 'Flat',
    ...overrides,
  })

  const createLUTInfo = (overrides = {}) => ({
    camera_model: 'Canon EOS 2000D',
    generated_at: '2026-07-12T12:30:00Z',
    match_quality: 0.87,
    exposure_offset_ev: -0.15,
    saturation_multiplier: 1.08,
    picture_control_hint: 'Neutral',
    ...overrides,
  })

  const createCaptureHints = (overrides = {}) => ({
    has_reference: true,
    picture_control: 'Neutral',
    parameters: { sharpening: 2, contrast: 1, saturation: 1 },
    wb_kelvin_hint: 5600,
    wb_tint_hint: 0,
    ev_hint: -0.15,
    match_quality: 0.87,
    ...overrides,
  })

  // ============================================================================
  // Disabled State Tests
  // ============================================================================

  describe('Disabled State', () => {
    it('should show disabled message when enabled is false', () => {
      render(<SiteLookCard data={{ enabled: false }} cameraModel="Nikon Z30" />)
      expect(screen.getByText(/site-wide look matching er deaktiveret/i)).toBeInTheDocument()
    })

    it('should show disabled message when data is null', () => {
      render(<SiteLookCard data={null} cameraModel="Nikon Z30" />)
      expect(screen.getByText(/site-wide look matching er deaktiveret/i)).toBeInTheDocument()
    })

    it('should not show any cards when disabled', () => {
      render(<SiteLookCard data={{ enabled: false }} cameraModel="Nikon Z30" />)
      expect(screen.queryByText(/Site Reference/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/Kamera LUT/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/Capture Hints/i)).not.toBeInTheDocument()
    })
  })

  // ============================================================================
  // No Reference State Tests
  // ============================================================================

  describe('No Reference State', () => {
    it('should show "Mangler Site Reference" when no reference exists', () => {
      const data = createMockData({ has_site_reference: false })
      render(<SiteLookCard data={data} cameraModel="Nikon Z30" />)
      expect(screen.getByText(/Mangler Site Reference/i)).toBeInTheDocument()
    })

    it('should show warning message about independent camera operation', () => {
      const data = createMockData({ has_site_reference: false })
      render(<SiteLookCard data={data} cameraModel="Nikon Z30" />)
      expect(screen.getByText(/Kameraer arbejder uafhængigt/i)).toBeInTheDocument()
    })

    it('should show amber warning color when no reference', () => {
      const { container } = render(
        <SiteLookCard data={createMockData({ has_site_reference: false })} cameraModel="Nikon Z30" />
      )
      const statusDiv = container.querySelector('.border-amber-200')
      expect(statusDiv).toBeInTheDocument()
    })

    it('should show "Opret Site Reference" button when callback provided', () => {
      const onSetReference = jest.fn()
      const data = createMockData({ has_site_reference: false })
      render(
        <SiteLookCard data={data} cameraModel="Nikon Z30" onSetReference={onSetReference} />
      )
      expect(screen.getByText(/Opret Site Reference/i)).toBeInTheDocument()
    })

    it('should not show "Opret Site Reference" button when no callback', () => {
      const data = createMockData({ has_site_reference: false })
      render(<SiteLookCard data={data} cameraModel="Nikon Z30" />)
      expect(screen.queryByText(/Opret Site Reference/i)).not.toBeInTheDocument()
    })

    it('should call onSetReference when button clicked', () => {
      const onSetReference = jest.fn()
      const data = createMockData({ has_site_reference: false })
      render(
        <SiteLookCard data={data} cameraModel="Nikon Z30" onSetReference={onSetReference} />
      )
      screen.getByText(/Opret Site Reference/i).click()
      expect(onSetReference).toHaveBeenCalledTimes(1)
    })
  })

  // ============================================================================
  // Reference Active State Tests
  // ============================================================================

  describe('Reference Active State', () => {
    it('should show "Site Reference Aktiv" when reference exists', () => {
      const refInfo = createReferenceInfo()
      const data = createMockData({
        has_site_reference: true,
        reference_info: refInfo,
      })
      render(<SiteLookCard data={data} cameraModel="Nikon Z30" />)
      expect(screen.getByText(/Site Reference Aktiv/i)).toBeInTheDocument()
    })

    it('should show "Alle kameraer matcher til fælles reference" message', () => {
      const refInfo = createReferenceInfo()
      const data = createMockData({
        has_site_reference: true,
        reference_info: refInfo,
      })
      render(<SiteLookCard data={data} cameraModel="Nikon Z30" />)
      expect(screen.getByText(/Alle kameraer matcher til fælles reference/i)).toBeInTheDocument()
    })

    it('should show green success color when reference exists', () => {
      const { container } = render(
        <SiteLookCard
          data={createMockData({
            has_site_reference: true,
            reference_info: createReferenceInfo(),
          })}
          cameraModel="Nikon Z30"
        />
      )
      const statusDiv = container.querySelector('.border-emerald-200')
      expect(statusDiv).toBeInTheDocument()
    })

    it('should show "✨ Denne billede er reference" badge when is_site_reference is true', () => {
      const data = createMockData({
        has_site_reference: true,
        is_site_reference: true,
        reference_info: createReferenceInfo(),
      })
      render(<SiteLookCard data={data} cameraModel="Nikon Z30" />)
      expect(screen.getByText(/✨ Denne billede er reference/i)).toBeInTheDocument()
    })

    it('should not show badge when is_site_reference is false', () => {
      const data = createMockData({
        has_site_reference: true,
        is_site_reference: false,
        reference_info: createReferenceInfo(),
      })
      render(<SiteLookCard data={data} cameraModel="Nikon Z30" />)
      expect(screen.queryByText(/✨ Denne billede er reference/i)).not.toBeInTheDocument()
    })
  })

  // ============================================================================
  // Reference Info Display Tests
  // ============================================================================

  describe('Reference Info Display', () => {
    it('should display site ID', () => {
      const refInfo = createReferenceInfo({ site_id: 'test-site-123' })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, reference_info: refInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/test-site-123/)).toBeInTheDocument()
    })

    it('should display camera that created reference', () => {
      const refInfo = createReferenceInfo({ created_by_camera: 'Canon EOS 2000D' })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, reference_info: refInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/Canon EOS 2000D/)).toBeInTheDocument()
    })

    it('should display quality score with proper formatting', () => {
      const refInfo = createReferenceInfo({ quality_score: 92.5 })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, reference_info: refInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/92.5%/)).toBeInTheDocument()
    })

    it('should show emerald color for high quality (>=85%)', () => {
      const { container } = render(
        <SiteLookCard
          data={createMockData({
            has_site_reference: true,
            reference_info: createReferenceInfo({ quality_score: 90 }),
          })}
          cameraModel="Nikon Z30"
        />
      )
      expect(container.querySelector('.text-emerald-600')).toBeInTheDocument()
    })

    it('should show sky color for medium quality (<85%)', () => {
      const { container } = render(
        <SiteLookCard
          data={createMockData({
            has_site_reference: true,
            reference_info: createReferenceInfo({ quality_score: 80 }),
          })}
          cameraModel="Nikon Z30"
        />
      )
      expect(container.querySelector('.text-sky-600')).toBeInTheDocument()
    })

    it('should display scene type label', () => {
      const refInfo = createReferenceInfo({ scene_type: 'golden_hour' })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, reference_info: refInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/Gyldent time/i)).toBeInTheDocument()
    })

    it('should display unknown scene type fallback', () => {
      const refInfo = createReferenceInfo({ scene_type: 'unknown_scene' })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, reference_info: refInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/unknown_scene/i)).toBeInTheDocument()
    })

    it('should display Picture Control with icon', () => {
      const refInfo = createReferenceInfo({ picture_control: 'Flat' })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, reference_info: refInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/Flat/)).toBeInTheDocument()
    })

    it('should format creation date correctly', () => {
      const refInfo = createReferenceInfo({ created_at: '2026-07-12T14:30:00Z' })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, reference_info: refInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/Opretet:/)).toBeInTheDocument()
    })
  })

  // ============================================================================
  // LUT Info Display Tests
  // ============================================================================

  describe('LUT Info Display', () => {
    it('should display camera model', () => {
      const lutInfo = createLUTInfo({ camera_model: 'Canon EOS 2000D' })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, lut_info: lutInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/Canon EOS 2000D/)).toBeInTheDocument()
    })

    it('should display match quality as percentage', () => {
      const lutInfo = createLUTInfo({ match_quality: 0.87 })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, lut_info: lutInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/87.0%/)).toBeInTheDocument()
    })

    it('should show emerald color for excellent match (>=90%)', () => {
      const { container } = render(
        <SiteLookCard
          data={createMockData({
            has_site_reference: true,
            lut_info: createLUTInfo({ match_quality: 0.92 }),
          })}
          cameraModel="Nikon Z30"
        />
      )
      expect(container.querySelector('.text-emerald-600')).toBeInTheDocument()
    })

    it('should show sky color for good match (>=75%)', () => {
      const { container } = render(
        <SiteLookCard
          data={createMockData({
            has_site_reference: true,
            lut_info: createLUTInfo({ match_quality: 0.80 }),
          })}
          cameraModel="Nikon Z30"
        />
      )
      expect(container.querySelector('.text-sky-600')).toBeInTheDocument()
    })

    it('should show amber color for fair match (>=60%)', () => {
      const { container } = render(
        <SiteLookCard
          data={createMockData({
            has_site_reference: true,
            lut_info: createLUTInfo({ match_quality: 0.65 }),
          })}
          cameraModel="Nikon Z30"
        />
      )
      expect(container.querySelector('.text-amber-600')).toBeInTheDocument()
    })

    it('should show red color for poor match (<60%)', () => {
      const { container } = render(
        <SiteLookCard
          data={createMockData({
            has_site_reference: true,
            lut_info: createLUTInfo({ match_quality: 0.50 }),
          })}
          cameraModel="Nikon Z30"
        />
      )
      expect(container.querySelector('.text-red-600')).toBeInTheDocument()
    })

    it('should format positive EV correctly', () => {
      const lutInfo = createLUTInfo({ exposure_offset_ev: 0.3 })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, lut_info: lutInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/\+0.30 EV/)).toBeInTheDocument()
    })

    it('should format negative EV correctly', () => {
      const lutInfo = createLUTInfo({ exposure_offset_ev: -0.15 })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, lut_info: lutInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/-0.15 EV/)).toBeInTheDocument()
    })

    it('should format zero EV as "0"', () => {
      const lutInfo = createLUTInfo({ exposure_offset_ev: 0 })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, lut_info: lutInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/0\b/)).toBeInTheDocument()
    })

    it('should highlight significant EV offset', () => {
      const { container } = render(
        <SiteLookCard
          data={createMockData({
            has_site_reference: true,
            lut_info: createLUTInfo({ exposure_offset_ev: -0.5 }),
          })}
          cameraModel="Nikon Z30"
        />
      )
      expect(container.querySelector('.text-amber-600')).toBeInTheDocument()
    })

    it('should display saturation multiplier', () => {
      const lutInfo = createLUTInfo({ saturation_multiplier: 1.08 })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, lut_info: lutInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/1.080x/)).toBeInTheDocument()
    })

    it('should highlight significant saturation change', () => {
      const { container } = render(
        <SiteLookCard
          data={createMockData({
            has_site_reference: true,
            lut_info: createLUTInfo({ saturation_multiplier: 1.2 }),
          })}
          cameraModel="Nikon Z30"
        />
      )
      expect(container.querySelector('.text-amber-600')).toBeInTheDocument()
    })

    it('should display Picture Control hint', () => {
      const lutInfo = createLUTInfo({ picture_control_hint: 'Neutral' })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, lut_info: lutInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/Neutral/)).toBeInTheDocument()
    })
  })

  // ============================================================================
  // Capture Hints Display Tests
  // ============================================================================

  describe('Capture Hints Display', () => {
    it('should display Picture Control hint', () => {
      const hints = createCaptureHints({ picture_control: 'Flat' })
      render(
        <SiteLookCard
          data={createMockData({ capture_hints: hints })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/Flat/)).toBeInTheDocument()
    })

    it('should display white balance hint when available', () => {
      const hints = createCaptureHints({ wb_kelvin_hint: 5600 })
      render(
        <SiteLookCard
          data={createMockData({ capture_hints: hints })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/5600K/)).toBeInTheDocument()
    })

    it('should not display WB hint when null', () => {
      const hints = createCaptureHints({ wb_kelvin_hint: null })
      render(
        <SiteLookCard
          data={createMockData({ capture_hints: hints })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.queryByText(/\d+K/)).not.toBeInTheDocument()
    })

    it('should display EV hint when significant', () => {
      const hints = createCaptureHints({ ev_hint: -0.3 })
      render(
        <SiteLookCard
          data={createMockData({ capture_hints: hints })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/-0.30 EV/)).toBeInTheDocument()
    })

    it('should not display EV hint when negligible', () => {
      const hints = createCaptureHints({ ev_hint: 0.005 })
      render(
        <SiteLookCard
          data={createMockData({ capture_hints: hints })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.queryByText(/EV/)).not.toBeInTheDocument()
    })

    it('should display Picture Control parameters', () => {
      const hints = createCaptureHints({
        parameters: { sharpening: 3, contrast: 0, saturation: 0 },
      })
      render(
        <SiteLookCard
          data={createMockData({ capture_hints: hints })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/sharpening: 3/)).toBeInTheDocument()
      expect(screen.getByText(/contrast: 0/)).toBeInTheDocument()
      expect(screen.getByText(/saturation: 0/)).toBeInTheDocument()
    })

    it('should not display parameters section when empty', () => {
      const hints = createCaptureHints({ parameters: {} })
      render(
        <SiteLookCard
          data={createMockData({ capture_hints: hints })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.queryByText(/Picture Control parametre/i)).not.toBeInTheDocument()
    })
  })

  // ============================================================================
  // Camera-Specific Recommendations Tests
  // ============================================================================

  describe('Camera-Specific Recommendations', () => {
    it('should display Nikon-specific info for Nikon cameras', () => {
      render(<SiteLookCard data={createMockData()} cameraModel="Nikon Z30" />)
      expect(screen.getByText(/Nikon Picture Controls/i)).toBeInTheDocument()
      expect(screen.getByText(/Flat anbefales/i)).toBeInTheDocument()
    })

    it('should display Canon-specific info for Canon cameras', () => {
      render(<SiteLookCard data={createMockData()} cameraModel="Canon EOS 2000D" />)
      expect(screen.getByText(/Canon Picture Styles/i)).toBeInTheDocument()
      expect(screen.getByText(/Neutral anbefales/i)).toBeInTheDocument()
    })

    it('should handle mixed case camera model names', () => {
      render(<SiteLookCard data={createMockData()} cameraModel="NIKON Z30" />)
      expect(screen.getByText(/Nikon Picture Controls/i)).toBeInTheDocument()
    })

    it('should not show specific info for unknown cameras', () => {
      render(<SiteLookCard data={createMockData()} cameraModel="Unknown Camera" />)
      expect(screen.queryByText(/Picture Controls/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/Picture Styles/i)).not.toBeInTheDocument()
    })
  })

  // ============================================================================
  // Action Buttons Tests
  // ============================================================================

  describe('Action Buttons', () => {
    it('should show "Opret Site Reference" button when no reference', () => {
      const onSetReference = jest.fn()
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: false })}
          cameraModel="Nikon Z30"
          onSetReference={onSetReference}
        />
      )
      expect(screen.getByText(/Opret Site Reference/i)).toBeInTheDocument()
    })

    it('should show "Regenerer Kamera LUT" button when reference exists', () => {
      const onRegenerateLUT = jest.fn()
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true })}
          cameraModel="Nikon Z30"
          onRegenerateLUT={onRegenerateLUT}
        />
      )
      expect(screen.getByText(/Regenerer Kamera LUT/i)).toBeInTheDocument()
    })

    it('should call onRegenerateLUT when button clicked', () => {
      const onRegenerateLUT = jest.fn()
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true })}
          cameraModel="Nikon Z30"
          onRegenerateLUT={onRegenerateLUT}
        />
      )
      screen.getByText(/Regenerer Kamera LUT/i).click()
      expect(onRegenerateLUT).toHaveBeenCalledTimes(1)
    })

    it('should not show "Regenerer Kamera LUT" when no callback', () => {
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.queryByText(/Regenerer Kamera LUT/i)).not.toBeInTheDocument()
    })
  })

  // ============================================================================
  // Error State Tests
  // ============================================================================

  describe('Error State', () => {
    it('should display error message when error present', () => {
      const data = createMockData({ error: 'Failed to load reference' })
      render(<SiteLookCard data={data} cameraModel="Nikon Z30" />)
      expect(screen.getByText(/Fejl under look matching/i)).toBeInTheDocument()
      expect(screen.getByText(/Failed to load reference/)).toBeInTheDocument()
    })

    it('should show error in red', () => {
      const { container } = render(
        <SiteLookCard
          data={createMockData({ error: 'Test error' })}
          cameraModel="Nikon Z30"
        />
      )
      expect(container.querySelector('.bg-red-50')).toBeInTheDocument()
    })

    it('should show alert icon for error', () => {
      render(<SiteLookCard data={createMockData({ error: 'Test error' })} cameraModel="Nikon Z30" />)
      expect(screen.getByTestId('alert-circle')).toBeInTheDocument()
    })
  })

  // ============================================================================
  // Edge Cases Tests
  // ============================================================================

  describe('Edge Cases', () => {
    it('should handle missing optional fields gracefully', () => {
      const data = {
        enabled: true,
        has_site_reference: true,
        // Missing optional fields
      }
      render(<SiteLookCard data={data} cameraModel="Nikon Z30" />)
      expect(screen.getByText(/Site Reference Aktiv/i)).toBeInTheDocument()
    })

    it('should handle undefined capture hints', () => {
      render(
        <SiteLookCard
          data={createMockData({ capture_hints: undefined })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.queryByText(/Capture Hints/i)).not.toBeInTheDocument()
    })

    it('should handle null reference info', () => {
      render(
        <SiteLookCard
          data={createMockData({ reference_info: null })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.queryByText(/Site Reference Info/i)).not.toBeInTheDocument()
    })

    it('should handle null LUT info', () => {
      render(
        <SiteLookCard
          data={createMockData({ lut_info: null })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.queryByText(/Kamera LUT/i)).not.toBeInTheDocument()
    })

    it('should handle empty parameters object', () => {
      const hints = createCaptureHints({ parameters: {} })
      render(
        <SiteLookCard
          data={createMockData({ capture_hints: hints })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.queryByText(/Picture Control parametre/i)).not.toBeInTheDocument()
    })

    it('should handle zero match quality', () => {
      const lutInfo = createLUTInfo({ match_quality: 0 })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, lut_info: lutInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/0.0%/)).toBeInTheDocument()
    })

    it('should handle perfect match quality', () => {
      const lutInfo = createLUTInfo({ match_quality: 1.0 })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, lut_info: lutInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/100.0%/)).toBeInTheDocument()
    })

    it('should handle extreme EV values', () => {
      const lutInfo = createLUTInfo({ exposure_offset_ev: -2.0 })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, lut_info: lutInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/-2.00 EV/)).toBeInTheDocument()
    })

    it('should handle extreme saturation values', () => {
      const lutInfo = createLUTInfo({ saturation_multiplier: 2.0 })
      render(
        <SiteLookCard
          data={createMockData({ has_site_reference: true, lut_info: lutInfo })}
          cameraModel="Nikon Z30"
        />
      )
      expect(screen.getByText(/2.000x/)).toBeInTheDocument()
    })
  })

  // ============================================================================
  // Accessibility Tests
  // ============================================================================

  describe('Accessibility', () => {
    it('should have proper heading hierarchy', () => {
      render(
        <SiteLookCard
          data={createMockData({
            has_site_reference: true,
            reference_info: createReferenceInfo(),
            lut_info: createLUTInfo(),
            capture_hints: createCaptureHints(),
          })}
          cameraModel="Nikon Z30"
        />
      )
      const headings = screen.getAllByRole('heading', { level: 4 })
      expect(headings.length).toBeGreaterThan(0)
    })

    it('should display camera model for context', () => {
      render(<SiteLookCard data={createMockData()} cameraModel="Nikon Z30" />)
      expect(screen.getByText(/Nikon Z30/)).toBeInTheDocument()
    })
  })
})
