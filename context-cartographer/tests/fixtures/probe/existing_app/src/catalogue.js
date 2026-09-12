const days = new Map();

function forDate(date) {
  return days.get(date) || [];
}

module.exports = { forDate };
