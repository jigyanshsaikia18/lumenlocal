import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});

// jsdom has neither ResizeObserver nor non-zero layout boxes, so recharts'
// ResponsiveContainer (used by SAIV/SoLV trend charts) renders at 0x0 and
// skips its inner SVG entirely. Stub both so chart component tests can
// assert on real rendered output instead of an empty container.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}

const originalGetBoundingClientRect = Element.prototype.getBoundingClientRect;
Element.prototype.getBoundingClientRect = function (this: Element) {
  const rect = originalGetBoundingClientRect.call(this);
  if (rect.width === 0 && rect.height === 0) {
    return { ...rect, width: 600, height: 400, top: 0, left: 0, right: 600, bottom: 400 };
  }
  return rect;
};
