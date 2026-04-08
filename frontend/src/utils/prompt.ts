import type { StructuredPrompt, CompiledPrompt, WeightedTerm } from '../types/reverse';

function formatWeightedTerm(term: string, weight?: number | null): string {
  if (typeof weight === 'number' && weight !== 1) {
    return `(${term}:${weight.toFixed(1)})`;
  }
  return term;
}

/**
 * 将结构化提示词编译为可用于文生图的 prompt 文本
 * @param structured - 结构化提示词对象
 * @returns CompiledPrompt - 包含 positive 和 negative 的对象
 */
export function compileStructuredPrompt(structured?: StructuredPrompt): CompiledPrompt {
  if (!structured) {
    return { positive: '', negative: '' };
  }

  const parts: string[] = [];
  const { subject, scene, style, tech, negative } = structured;

  if (subject?.label) {
    parts.push(formatWeightedTerm(subject.label, subject.weight));
  }
  if (subject?.entities?.length) {
    parts.push(...subject.entities);
  }
  if (subject?.attributes) {
    if (Array.isArray(subject.attributes)) {
      parts.push(...subject.attributes);
    } else {
      parts.push(...Object.entries(subject.attributes).map(([key, value]) => `${key} ${value}`));
    }
  }

  if (scene?.environment?.length) parts.push(...scene.environment);
  if (scene?.background?.length) parts.push(...scene.background);
  if (scene?.time_weather?.length) parts.push(...scene.time_weather);
  if (scene?.composition?.length) parts.push(...scene.composition);

  if (style?.medium?.length) parts.push(...style.medium);
  if (style?.artist_style?.length) parts.push(...style.artist_style);
  if (style?.aesthetic?.length) parts.push(...style.aesthetic);
  if (style?.quality?.length) parts.push(...style.quality);

  if (tech?.lighting?.length) parts.push(...tech.lighting);
  if (tech?.camera?.length) parts.push(...tech.camera);
  if (tech?.color_tone?.length) parts.push(...tech.color_tone);
  if (tech?.render?.length) parts.push(...tech.render);

  const positive = parts.join(', ');

  const negativeParts: string[] = [];
  const seen = new Set<string>();

  const addTerm = (item: WeightedTerm | string) => {
    if (typeof item === 'string') {
      if (!seen.has(item)) {
        negativeParts.push(item);
        seen.add(item);
      }
      return;
    }
    if (item?.term && !seen.has(item.term)) {
      negativeParts.push(formatWeightedTerm(item.term, item.weight));
      seen.add(item.term);
    }
  };

  if (negative?.term_weights?.length) {
    negative.term_weights.forEach(addTerm);
  }
  if (negative?.terms?.length) {
    negative.terms.forEach(addTerm);
  }

  return { positive, negative: negativeParts.join(', ') };
}

/**
 * 复制文本到剪贴板
 * @param text - 要复制的文本
 * @returns Promise<boolean> - 是否成功
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    } else {
      // 降级方案：使用传统的 execCommand
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.left = '-999999px';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {
        document.execCommand('copy');
        textArea.remove();
        return true;
      } catch (error) {
        textArea.remove();
        return false;
      }
    }
  } catch (error) {
    console.error('复制失败:', error);
    return false;
  }
}
