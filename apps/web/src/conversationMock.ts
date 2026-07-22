/**
 * Mock conversation data for the M2 dialog skeleton.
 *
 * This is a static demonstration of the 8-stage collection flow per
 * docs/specs/m2/expert-conversation-workspace.md. Real persistence and
 * validation arrive with the M2 backend; this file lets the front-end
 * show a complete visual flow end-to-end.
 */

import type { ReactNode } from 'react'

export type MessageType = 'AGENT_PROMPT' | 'USER_DRAFT' | 'CONFIRMATION_CARD' | 'TOOL_CARD'
export type PresentationState =
  | 'PENDING'
  | 'VALIDATING'
  | 'BLOCKED'
  | 'WARNING_CONFIRMATION'
  | 'COMMITTED'
  | 'REVISION_CONFLICT'

export interface ConversationMessage {
  id: string
  messageType: MessageType
  stage: number // 1-8
  content: ReactNode
  // CONFIRMATION_CARD only:
  presentationState?: PresentationState
  canonicalValue?: string
  // TOOL_CARD only:
  taskId?: string
  taskStatus?: 'DISPATCH_PENDING' | 'QUEUED' | 'RUNNING' | 'SUCCEEDED'
}

export interface StageDef {
  id: number
  key: string
  titleZh: string
  titleEn: string
  hintZh: string
}

export const STAGES: StageDef[] = [
  { id: 1, key: 'project', titleZh: '产品 / 模板', titleEn: 'Product / Template', hintZh: '选择 PCB 产品模板，确认工厂地理信息' },
  { id: 2, key: 'geo', titleZh: '地理 / 气象', titleEn: 'Geography / Weather', hintZh: '坐标、时区、静态工况来源' },
  { id: 3, key: 'building', titleZh: '建筑 / 楼层', titleEn: 'Building / Floors', hintZh: '至少一栋一层，正面积 / 层高' },
  { id: 4, key: 'zone', titleZh: '区域 / 工序', titleEn: 'Zones / Processes', hintZh: '唯一工序绑定，主要工序全覆盖' },
  { id: 5, key: 'env', titleZh: '工艺环境', titleEn: 'Process Environment', hintZh: '硬规则阻断，经验超限警告放行需原因' },
  { id: 6, key: 'cooling', titleZh: '冷量输入', titleEn: 'Cooling Input', hintZh: 'SI 结构化确认；PCW 明确值或 0' },
  { id: 7, key: 'schedule', titleZh: '计划 / 蓄冷', titleEn: 'Schedule / Storage', hintZh: '主要工序计划无重叠；蓄冷只保存' },
  { id: 8, key: 'review', titleZh: '复核', titleEn: 'Review', hintZh: '阻断为 0、警告确认，冻结 revision' },
]

// Fixed HDI process chain (PRD 3.3). M2 spec mandates it appears on the
// right rail once stage 1 confirms HDI.
export const HDI_PROCESS_CHAIN = [
  { code: 'drill-fill', nameZh: '钻孔填孔', nameEn: 'Drill & Fill', major: true },
  { code: 'electroplating', nameZh: '电镀', nameEn: 'Electroplating', major: true },
  { code: 'laser-via', nameZh: '激光盲孔', nameEn: 'Laser Via', major: true },
  { code: 'pattern', nameZh: '线路制作', nameEn: 'Pattern', major: true },
  { code: 'etch', nameZh: '蚀刻', nameEn: 'Etch', major: true },
  { code: 'solder-mask', nameZh: '阻焊', nameEn: 'Solder Mask', major: false },
  { code: 'surface-finish', nameZh: '表面处理', nameEn: 'Surface Finish', major: false },
  { code: 'test', nameZh: '电测', nameEn: 'Test', major: true },
]
