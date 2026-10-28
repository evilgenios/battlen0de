import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '@/test/test-utils';
import { ImmersiveMissionSection } from './ImmersiveMissionSection';

describe('ImmersiveMissionSection', () => {
  it('renders every stage as real content and links directly to it', () => {
    renderWithProviders(<ImmersiveMissionSection />);

    expect(screen.getByText('Base telemetry')).toBeInTheDocument();
    expect(screen.getByText('Production Buildings')).toBeInTheDocument();
    expect(screen.getByText('Conquest Guard')).toBeInTheDocument();

    const operateLinks = screen.getAllByRole('link', { name: /operate/i });
    const protectLinks = screen.getAllByRole('link', { name: /protect/i });
    const observeLinks = screen.getAllByRole('link', { name: /observe/i });

    expect(operateLinks.some((link) => link.getAttribute('href') === '#experience-operate')).toBe(true);
    expect(protectLinks.some((link) => link.getAttribute('href') === '#experience-protect')).toBe(true);
    expect(observeLinks.some((link) => link.getAttribute('href') === '#experience-observe')).toBe(true);
  });
});
