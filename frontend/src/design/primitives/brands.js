import React from 'react';
import AlibabaCloudColor from '@lobehub/icons/es/AlibabaCloud/components/Color';
import AnthropicMono from '@lobehub/icons/es/Anthropic/components/Mono';
import AwsColor from '@lobehub/icons/es/Aws/components/Color';
import AzureColor from '@lobehub/icons/es/Azure/components/Color';
import BedrockColor from '@lobehub/icons/es/Bedrock/components/Color';
import CloudflareColor from '@lobehub/icons/es/Cloudflare/components/Color';
import DeepSeekColor from '@lobehub/icons/es/DeepSeek/components/Color';
import GeminiColor from '@lobehub/icons/es/Gemini/components/Color';
import GoogleCloudColor from '@lobehub/icons/es/GoogleCloud/components/Color';
import KimiColor from '@lobehub/icons/es/Kimi/components/Color';
import MicrosoftColor from '@lobehub/icons/es/Microsoft/components/Color';
import OllamaMono from '@lobehub/icons/es/Ollama/components/Mono';
import OpenAIMono from '@lobehub/icons/es/OpenAI/components/Mono';
import QwenColor from '@lobehub/icons/es/Qwen/components/Color';

const markStyle = { flexShrink: 0, display: 'block' };

const OracleMark = ({ size = '1em', style, ...rest }) => (
  <svg
    height={size}
    width={size}
    viewBox="0 0 24 24"
    style={{ flex: 'none', lineHeight: 1, ...markStyle, ...style }}
    xmlns="http://www.w3.org/2000/svg"
    {...rest}
  >
    <title>Oracle</title>
    <path
      d="M8.2 7.2h7.6C19.2 7.2 22 9.8 22 12.8S19.2 18.4 15.8 18.4H8.2C4.8 18.4 2 15.8 2 12.8S4.8 7.2 8.2 7.2zm0 2.4C6.2 9.6 4.6 11 4.6 12.8S6.2 16 8.2 16h7.6c2 0 3.6-1.4 3.6-3.2S17.8 9.6 15.8 9.6H8.2z"
      fill="#C74632"
    />
  </svg>
);

const LinuxMark = ({ size = '1em', style, ...rest }) => (
  <svg
    height={size}
    width={size}
    viewBox="0 0 24 24"
    style={{ flex: 'none', lineHeight: 1, ...markStyle, ...style }}
    xmlns="http://www.w3.org/2000/svg"
    {...rest}
  >
    <title>Linux</title>
    <ellipse cx="12" cy="16.6" rx="7.2" ry="5.2" fill="#1a1a1a" />
    <circle cx="12" cy="8.6" r="5.1" fill="#1a1a1a" />
    <ellipse cx="12" cy="17.4" rx="4.2" ry="3.2" fill="#f5f5f5" />
    <circle cx="10.2" cy="7.8" r="1.05" fill="#f5f5f5" />
    <circle cx="13.8" cy="7.8" r="1.05" fill="#f5f5f5" />
    <circle cx="10.2" cy="8" r="0.45" fill="#1a1a1a" />
    <circle cx="13.8" cy="8" r="0.45" fill="#1a1a1a" />
    <path d="M10.4 10.2L12 12.4L13.6 10.2Z" fill="#FCC624" />
    <path d="M7.1 20.4c.7 1.4 2.4 2.2 4.9 2.2s4.2-.8 4.9-2.2" fill="#FCC624" />
  </svg>
);

const ICONS = {
  cloudflare: { title: 'Cloudflare', Icon: CloudflareColor },
  route53: { title: 'Amazon Route 53', Icon: AwsColor },
  alidns: { title: 'Alibaba Cloud', Icon: AlibabaCloudColor },
  azure: { title: 'Microsoft Azure', Icon: AzureColor },
  gcp: { title: 'Google Cloud', Icon: GoogleCloudColor },
  windows: { title: 'Windows', Icon: MicrosoftColor },
  linux: { title: 'Linux', Icon: LinuxMark },
  anthropic: { title: 'Anthropic', Icon: AnthropicMono },
  openai: { title: 'OpenAI', Icon: OpenAIMono },
  gemini: { title: 'Google Gemini', Icon: GeminiColor },
  kimi: { title: 'Kimi', Icon: KimiColor },
  qwen: { title: 'Qwen', Icon: QwenColor },
  deepseek: { title: 'DeepSeek', Icon: DeepSeekColor },
  bedrock: { title: 'AWS Bedrock', Icon: BedrockColor },
  oracle: { title: 'Oracle', Icon: OracleMark },
  local: { title: 'RAPTOR Local', Icon: OllamaMono }
};

const ALIASES = {
  openai_compat: 'openai',
  anthropic_compat: 'anthropic',
  aws: 'bedrock',
  moonshot: 'kimi',
  dashscope: 'qwen',
  raptor: 'local',
  'raptor-local': 'local',
  ollama: 'local',
  microsoft: 'windows',
  win: 'windows'
};

export const ProviderMark = ({ type, size = 18 }) => {
  const key = String(type || '').toLowerCase();
  const icon = ICONS[key] || ICONS[ALIASES[key]];
  if (!icon) return null;
  const { Icon, title } = icon;
  return <Icon size={size} role="img" aria-label={title} style={markStyle} />;
};

export const OsMark = ({ type, size = 16 }) => <ProviderMark type={type} size={size} />;

export default ProviderMark;
