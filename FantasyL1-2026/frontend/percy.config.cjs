/** @type {import('@percy/cli').Config} */
module.exports = {
  version: 2,
  snapshot: {
    widths: [390, 1280],
    minHeight: 720
  },
  discovery: {
    allowedHostnames: ["127.0.0.1", "localhost"]
  }
};
