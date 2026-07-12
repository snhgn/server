import { createGitHubOAuthFlow } from '@keystatic/core/oauth/github';
import config from '../../../keystatic.config';

export const ALL = createGitHubOAuthFlow(config);
