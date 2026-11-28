// Work-order insert shown only while the directed watch has handed controls to the crew.
import {repairReportLines} from './repair_report.js';
import {getPhotoBlob} from '../collection_store.js';
import {titleCard} from '../brand/chapter_card.js';
import {chapterCardData} from '../brand/chapters.js';
import {STRINGS} from './cable_copy.js';

export function showCableHandover(stage, state) {
  const chapter = state.campaign.chapter;
  const second = chapter === 'c4_frame';
  const beat = state.campaign.node;
  const closing = !beat.location;
  const sheet = chapterCardData({id: chapter, title: second ? STRINGS.sub2 : STRINGS.sub1});
  sheet.number = second ? STRINGS.site2 : STRINGS.site1;
  const records = Object.values(state.repair_report.observations);
  const last = records.at(-1);
  if (closing && last) {
    sheet.title = last.photo;
    sheet.sub = `T+${last.t} s   /   ${last.depth_m} m`;
    if (state.repair_report.end_separation_m != null) sheet.sub += `   /   Δ ${state.repair_report.end_separation_m} m`;
  }
  // An unlinked camera record still has a valid log entry. Leave the photo side as line art.
  if (closing) sheet.scenario = '';
  const insert = titleCard(sheet);
  if (closing) {
    const log = document.createElement('div');
    log.className = 'cable-evidence-log';
    for (const line of repairReportLines(state.repair_report)) {
      const row = document.createElement('p');
      row.textContent = line;
      log.append(row);
    }
    insert.querySelector('.brand-card-symbol').replaceChildren(log);
  }
  insert.classList.add('cable-work-order');
  stage.root.insertBefore(insert, stage.bars);
  let objectUrl;
  if (closing && last?.collection_id) {
    getPhotoBlob(last.collection_id).then(function showOriginal(blob) {
      if (!insert.isConnected) return;
      objectUrl = URL.createObjectURL(blob);
      const half = insert.querySelector('.brand-card-photo');
      const image = document.createElement('img');
      image.alt = last.photo;
      image.onload = () => { half.dataset.plate = ''; };
      image.src = objectUrl;
      half.append(image);
    }).catch(function keepReferencePlate() {});
  }
  return function removeInsert() {
    insert.remove();
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  };
}
