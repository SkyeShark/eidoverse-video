// MIT. Setup datums for the captured-jaw, sliding-tailstock G430 fixture.
export function rotaryFixtureSetup({
  stockLength = .140,
  stockWidth = .036,
  stockHeight = .036,
  quill = 0,
} = {}) {
  if (![stockLength, stockWidth, stockHeight, quill].every(Number.isFinite)) {
    throw Error("Rotary stock dimensions and quill travel must be finite");
  }
  if (
    stockLength < .080 - 1e-9 || stockLength > .180 + 1e-9 ||
    Math.min(stockWidth, stockHeight) < .018 - 1e-9 ||
    Math.max(stockWidth, stockHeight) > .050 + 1e-9
  ) {
    throw Error("Fixture accepts 80–180 mm long stock, 18–50 mm wide and high");
  }
  const tailstock = stockLength - .140 - quill;
  if (
    Math.abs(quill) > .006 + 1e-9 || tailstock < -.060 - 1e-9 ||
    tailstock > .040 + 1e-9
  ) {
    throw Error("Tailstock carriage or quill exceeds its captured travel");
  }
  return {
    stockLength,
    stockWidth,
    stockHeight,
    quill,
    axisX: -.055 + stockLength / 2,
    axisHeight: .097,
    start: -stockLength / 2 + .029,
    end: stockLength / 2 - .018,
    joints: {
      rotary_tailstock: tailstock,
      rotary_quill: quill,
      rotary_handwheel: -quill / .001 * 2 * Math.PI,
      rotary_jaw_0: stockHeight / 2 - .018,
      rotary_jaw_2: stockHeight / 2 - .018,
      rotary_jaw_1: stockWidth / 2 - .018,
      rotary_jaw_3: stockWidth / 2 - .018,
    },
  };
}
