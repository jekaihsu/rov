// Career data loader: the YX work orders (contracts.json), licence grades (licences.json), the equipment
// department catalogue (equipment.json) and the repair price table (repair_prices.json), fetched once next to
// this module and joined into one object that the pure rules (rules.js, scoring.js, repair.js) take as an
// argument. Tests build the same object with careerDataFrom().

let pending = null;

/** Joins the parsed files into the data object the rules use. */
export function careerDataFrom({ contractsFile, licencesFile, equipmentFile, repairPricesFile = null }) {
  const contracts = [...(contractsFile?.contracts || [])].sort(function byChapterOrder(a, b) {
    const chapters = (contractsFile?.chapters || []).map(function chapterId(entry) {
      return entry.id;
    });
    return chapters.indexOf(a.chapter) - chapters.indexOf(b.chapter) || a.order - b.order;
  });
  return {
    clients: contractsFile?.clients || {},
    jobs: contractsFile?.jobs || {},
    chapters: contractsFile?.chapters || [],
    contracts,
    grades: licencesFile?.grades || [],
    endorsements: licencesFile?.endorsements || [],
    items: equipmentFile?.items || [],
    repairPrices: repairPricesFile || null,
  };
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

/** The career data for the page, loaded once. */
export function loadCareerData() {
  if (pending) return pending;
  const base = new URL('./', import.meta.url);
  pending = Promise.all([
    fetchJson(new URL('contracts.json', base)),
    fetchJson(new URL('licences.json', base)),
    fetchJson(new URL('equipment.json', base)),
    fetchJson(new URL('repair_prices.json', base)),
  ]).then(function join([contractsFile, licencesFile, equipmentFile, repairPricesFile]) {
    return careerDataFrom({ contractsFile, licencesFile, equipmentFile, repairPricesFile });
  });
  pending.catch(function retryLater() {
    pending = null;
  });
  return pending;
}
