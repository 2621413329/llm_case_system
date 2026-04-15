import { getJson } from './http';
import { postJson } from './http';

export async function generateAnalysisByHistoryId(historyId) {
  return getJson(`/api/analyze/${Number(historyId)}`, '分析生成失败');
}

export async function generateOcrManualDraft(historyId) {
  return getJson(`/api/ocr/manual/${Number(historyId)}`, 'OCR建议生成失败');
}

export async function searchRequirementElements(payload) {
  return postJson('/api/requirement/network/search', payload || {});
}
