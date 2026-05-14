export function nextModalFocusIndex(
  currentIndex: number,
  focusableCount: number,
  backwards: boolean,
): number {
  if (focusableCount <= 0) return -1;
  if (currentIndex < 0) return backwards ? focusableCount - 1 : 0;
  if (backwards) return currentIndex === 0 ? focusableCount - 1 : currentIndex - 1;
  return currentIndex === focusableCount - 1 ? 0 : currentIndex + 1;
}
