import React from 'react';
import { AbsoluteFill, Composition, Img, useCurrentFrame, useVideoConfig } from 'remotion';
import { RenderConfigDTO } from '@animal-puzzle/shared';

export function evaluatePeriodicDisplacement(phase0to1: number, holdRatio = 0.14): number {
  const p = ((phase0to1 % 1) + 1) % 1;
  const halfHold = Math.min(0.18, Math.max(0.02, holdRatio * 0.5));
  if (p < halfHold || p > 1 - halfHold) return 0;
  if (Math.abs(p - 0.5) < halfHold) return 0;
  if (p < 0.5) {
    const u = (p - halfHold) / (0.5 - 2 * halfHold);
    return Math.sin(u * Math.PI);
  }
  const u = (p - (0.5 + halfHold)) / (0.5 - 2 * halfHold);
  return -Math.sin(u * Math.PI);
}

export const OutlineMatchComposition: React.FC<{ config: RenderConfigDTO; animalUrl: string; outlineUrl: string; eggUrl: string; eggOutlineUrl: string }> = ({
  config,
  animalUrl,
  outlineUrl,
  eggUrl,
  eggOutlineUrl,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width } = useVideoConfig();
  const phase = (frame / durationInFrames) * config.cycles;
  const disp = evaluatePeriodicDisplacement(phase, config.holdRatio);
  const dx = Math.round(disp * config.offsetDistancePx);

  const slots = [
    { x: width / 2, y: 935, scale: 1.06 },
    { x: width / 2, y: 1210, scale: 1.06 },
    { x: width / 2 - 215, y: 1485, scale: 0.88 },
    { x: width / 2, y: 1495, scale: 1.06 },
    { x: width / 2 + 215, y: 1485, scale: 0.88 },
  ].slice(0, config.objectCount);

  return (
    <AbsoluteFill style={{ backgroundColor: config.backgroundHex }}>
      <Img src={outlineUrl} style={{ position: 'absolute', left: (width - 720) / 2, top: 165, width: 720, height: 640 }} />
      {slots.map((s, i) => (
        <React.Fragment key={i}>
          <Img src={eggOutlineUrl} style={{ position: 'absolute', left: s.x - 102 * s.scale, top: s.y - 126 * s.scale, width: 205 * s.scale, height: 252 * s.scale }} />
          <Img src={eggUrl} style={{ position: 'absolute', left: s.x - 102 * s.scale + dx * (1 + 0.08 * ((i + config.seed) % 3 - 1)), top: s.y - 126 * s.scale, width: 205 * s.scale, height: 252 * s.scale }} />
        </React.Fragment>
      ))}
      <Img src={animalUrl} style={{ position: 'absolute', left: (width - 720) / 2 + dx, top: 165, width: 720, height: 640 }} />
    </AbsoluteFill>
  );
};

export const MissingPieceSlideComposition: React.FC<{ config: RenderConfigDTO; baseAnimalUrl: string; pieceUrl: string; targetX: number; targetY: number; pieceW: number; pieceH: number }> = ({
  config,
  baseAnimalUrl,
  pieceUrl,
  targetX,
  targetY,
  pieceW,
  pieceH,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, width, height } = useVideoConfig();
  const cycleP = ((frame / durationInFrames) * config.cycles) % 1;
  const holdW = config.holdRatio * 0.5;
  let normOffset = 0;
  if (Math.abs(cycleP - 0.5) <= holdW) {
    normOffset = 0;
  } else if (cycleP < 0.5 - holdW) {
    const u = cycleP / (0.5 - holdW);
    normOffset = -1 + Math.sin(u * Math.PI * 0.5);
  } else {
    const u = (cycleP - (0.5 + holdW)) / (0.5 - holdW);
    normOffset = 1 - Math.cos(u * Math.PI * 0.5);
  }
  if (config.direction === 'bottom_to_top') normOffset = -normOffset;
  const travelSpan = height / 2 + pieceH / 2 + 120;
  const curY = Math.round(targetY + normOffset * travelSpan);

  return (
    <AbsoluteFill style={{ backgroundColor: config.backgroundHex }}>
      <Img src={baseAnimalUrl} style={{ position: 'absolute', left: (width - 860) / 2, top: (height - 860) / 2 - 40, width: 860, height: 860 }} />
      <Img src={pieceUrl} style={{ position: 'absolute', left: targetX, top: curY, width: pieceW, height: pieceH }} />
    </AbsoluteFill>
  );
};
