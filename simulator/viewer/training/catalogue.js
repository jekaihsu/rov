// Pure course-map helpers over training/courses.json. Levels follow the company
// curriculum (docs/training/curriculum.md) and the research report's competency
// framing; pass criteria stay provisional until baseline flights calibrate them.
// Group labels requested by S6: 入門 / 操作員 / 進階 / 事故處置.

export const LEVEL_GROUPS = [
  {id: 'intro', source: '初級', kind: 'course'},
  {id: 'operator', source: '中級', kind: 'course'},
  {id: 'advanced', source: '進階', kind: 'course'},
  {id: 'incident', source: '事故', kind: 'incident'},
];

export function normalizeCourse(entry) {
  if (!entry || typeof entry !== 'object') return null;
  return {
    id: entry.id,
    title: entry.title || entry.id,
    scenario: entry.scenario,
    mode: entry.mode || 'scenario_training',
    category: entry.category || 'course',
    order: Number.isFinite(entry.order) ? entry.order : 0,
    level: entry.level || '',
    simulatorMinutes: entry.simulator_minutes ?? entry.simulatorMinutes ?? 60,
    goal: entry.goal || '',
    criteria: entry.criteria || '',
    passStatus: entry.pass_status || entry.passStatus || '',
    injection: entry.injection || '',
    sourceChapters: entry.source_chapters || entry.sourceChapters || [],
  };
}

export function allLessons(catalogue) {
  const courses = (catalogue?.courses || []).map(normalizeCourse).filter(Boolean);
  const incidents = (catalogue?.incidents || []).map(normalizeCourse).filter(Boolean);
  return [...courses, ...incidents];
}

export function lessonsByGroup(catalogue) {
  const lessons = allLessons(catalogue);
  return LEVEL_GROUPS.map(function group(definition) {
    const rows = lessons
      .filter(function match(lesson) {
        if (definition.kind === 'incident') return lesson.category === 'incident';
        return lesson.category === 'course' && lesson.level === definition.source;
      })
      .sort(function byOrder(a, b) {
        return a.order - b.order || a.id.localeCompare(b.id);
      });
    return {id: definition.id, source: definition.source, kind: definition.kind, lessons: rows};
  });
}

export function findLesson(catalogue, id) {
  return allLessons(catalogue).find(function byId(lesson) {
    return lesson.id === id;
  }) || null;
}
