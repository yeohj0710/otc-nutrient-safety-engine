/** PubMed의 철회 논문·철회 공지는 서지기록으로 보존하되 결과 근거로 쓰지 않는다. */
export function isRetractedPublication(publicationTypes: unknown): boolean {
  return typeof publicationTypes === "string" && publicationTypes.split("|").some(
    (type) => /^(?:Retracted Publication|Retraction of Publication)$/i.test(type.trim()),
  );
}

export const retractedPublicationNotice =
  "철회된 논문 또는 철회 공지입니다. 서지정보만 표시하며 결과 인용과 AI 요약에는 사용하지 않습니다.";
