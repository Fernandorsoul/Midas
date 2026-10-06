export function sparkline(values, label) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 110 32');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', label);
  const line = document.createElementNS(svg.namespaceURI, 'polyline');
  const low = Math.min(...values);
  const range = Math.max(...values) - low || 1;
  line.setAttribute('points', values.map((value, index) => `${index * 110 / (values.length - 1)},${30 - (value - low) / range * 27}`).join(' '));
  line.setAttribute('fill', 'none');
  line.setAttribute('stroke', '#a7bd88');
  line.setAttribute('stroke-width', '1.6');
  svg.append(line);
  return svg;
}
