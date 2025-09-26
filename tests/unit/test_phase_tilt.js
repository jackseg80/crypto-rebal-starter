import { applyPhaseTilt, getFeatureFlags, updateFeatureFlags } from '../../static/modules/targets-coordinator.js';

describe('Phase Tilt Feature', () => {
    const baseTargets = {
        'BTC': 35.0,
        'ETH': 25.0,
        'Stablecoins': 20.0,
        'SOL': 5.0,
        'L1/L0 majors': 7.0,
        'L2/Scaling': 4.0,
        'DeFi': 2.0,
        'AI/Data': 1.5,
        'Gaming/NFT': 0.5,
        'Memecoins': 0.0,
        'Others': 0.0,
        model_version: 'macro-2'
    };

    beforeEach(() => {
        // Reset feature flags to defaults
        updateFeatureFlags({
            ALTSEASON_TILT_ENABLED: true,
            ALTSEASON_TILT_MAX: 5.0,
            ALTSEASON_TILT_SOURCE: ['Stablecoins', 'BTC'],
            ALTSEASON_TILT_DESTINATION: 'Memecoins',
            ALTSEASON_TILT_AMOUNT: 2.0,
            ALTSEASON_TILT_MIN_PHASE_CONFIDENCE: 0.7
        });
    });

    test('should apply tilt when feature flag is enabled and phase is full_altseason', () => {
        const result = applyPhaseTilt(baseTargets, 'full_altseason', 0.8);

        expect(result.Memecoins).toBe(2.0); // +2% from 0%
        expect(result.Stablecoins).toBe(19.0); // -1% from 20%
        expect(result.BTC).toBe(34.0); // -1% from 35%
        expect(result.ETH).toBe(25.0); // unchanged
    });

    test('should not apply tilt when feature flag is disabled', () => {
        updateFeatureFlags({ ALTSEASON_TILT_ENABLED: false });

        const result = applyPhaseTilt(baseTargets, 'full_altseason', 0.8);

        expect(result).toEqual(baseTargets); // no changes
    });

    test('should not apply tilt when phase confidence is too low', () => {
        const result = applyPhaseTilt(baseTargets, 'full_altseason', 0.5);

        expect(result).toEqual(baseTargets); // no changes
    });

    test('should respect maximum tilt limit', () => {
        updateFeatureFlags({ ALTSEASON_TILT_AMOUNT: 10.0 }); // Try to set 10%

        const result = applyPhaseTilt(baseTargets, 'full_altseason', 0.8);

        expect(result.Memecoins).toBe(5.0); // Capped at 5% max
        expect(result.Stablecoins).toBe(17.5); // -2.5% from 20%
        expect(result.BTC).toBe(32.5); // -2.5% from 35%
    });

    test('should handle missing phase gracefully', () => {
        const result = applyPhaseTilt(baseTargets, null, 0.8);

        expect(result).toEqual(baseTargets); // no changes
    });

    test('should handle unknown phase gracefully', () => {
        const result = applyPhaseTilt(baseTargets, 'unknown_phase', 0.8);

        expect(result).toEqual(baseTargets); // no changes
    });

    test('should get feature flags correctly', () => {
        const flags = getFeatureFlags();

        expect(flags.ALTSEASON_TILT_ENABLED).toBe(true);
        expect(flags.ALTSEASON_TILT_MAX).toBe(5.0);
        expect(flags.ALTSEASON_TILT_SOURCE).toEqual(['Stablecoins', 'BTC']);
        expect(flags.ALTSEASON_TILT_DESTINATION).toBe('Memecoins');
    });

    test('should update feature flags securely', () => {
        updateFeatureFlags({
            ALTSEASON_TILT_ENABLED: false,
            ALTSEASON_TILT_AMOUNT: 3.0
        });

        const flags = getFeatureFlags();

        expect(flags.ALTSEASON_TILT_ENABLED).toBe(false);
        expect(flags.ALTSEASON_TILT_AMOUNT).toBe(3.0);
        // Other flags should remain unchanged
        expect(flags.ALTSEASON_TILT_MAX).toBe(5.0);
    });

    test('should ignore unknown feature flags during update', () => {
        const originalFlags = getFeatureFlags();

        updateFeatureFlags({
            UNKNOWN_FLAG: 'test',
            ALTSEASON_TILT_AMOUNT: 4.0
        });

        const flags = getFeatureFlags();

        expect(flags.ALTSEASON_TILT_AMOUNT).toBe(4.0);
        expect('UNKNOWN_FLAG' in flags).toBe(false);
        // Other flags should remain unchanged
        expect(flags.ALTSEASON_TILT_ENABLED).toBe(true);
    });

    test('should handle edge case with zero values', () => {
        const zeroTargets = {
            'BTC': 0.0,
            'ETH': 0.0,
            'Stablecoins': 100.0,
            'Memecoins': 0.0,
            model_version: 'test'
        };

        const result = applyPhaseTilt(zeroTargets, 'full_altseason', 0.8);

        expect(result.Memecoins).toBe(2.0); // +2% from 0%
        expect(result.Stablecoins).toBe(98.0); // -2% from 100%
        expect(result.BTC).toBe(0.0); // unchanged (0 - 1% = 0)
    });

    test('should maintain total allocation integrity', () => {
        const result = applyPhaseTilt(baseTargets, 'full_altseason', 0.8);

        const total = Object.entries(result)
            .filter(([key]) => key !== 'model_version')
            .reduce((sum, [, value]) => sum + value, 0);

        // Total should remain 100% (within rounding tolerance)
        expect(Math.abs(total - 100)).toBeLessThan(0.01);
    });
});