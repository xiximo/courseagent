import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type NodeChange,
  type NodeTypes,
  type OnSelectionChangeParams,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  formatEdgeCondition,
  graphToReactFlow,
  reactFlowToGraph,
  type WorkflowFlowNode,
  type WorkflowFlowEdgeData,
  type WorkflowGraph,
} from '../../lib/workflow-graph'
import { WorkflowAgentNode } from './workflow-agent-node'

const nodeTypes: NodeTypes = {
  agentNode: WorkflowAgentNode,
}

export type CanvasSelection =
  | { kind: 'node'; id: string }
  | { kind: 'edge'; id: string }
  | null

type WorkflowCanvasProps = {
  graph: WorkflowGraph
  selection: CanvasSelection
  readOnly?: boolean
  onGraphChange: (graph: WorkflowGraph) => void
  onSelectionChange: (selection: CanvasSelection) => void
}

function applySelectionFlags(
  nodes: WorkflowFlowNode[],
  edges: Edge[],
  selection: CanvasSelection
): { nodes: WorkflowFlowNode[]; edges: Edge[] } {
  const nodeId = selection?.kind === 'node' ? selection.id : null
  const edgeId = selection?.kind === 'edge' ? selection.id : null
  return {
    nodes: nodes.map((n) => ({ ...n, selected: nodeId === n.id })),
    edges: edges.map((e) => ({ ...e, selected: edgeId === e.id })),
  }
}

function WorkflowCanvasInner({
  graph,
  selection,
  readOnly,
  onGraphChange,
  onSelectionChange,
}: WorkflowCanvasProps) {
  const [nodes, setNodes] = useState<WorkflowFlowNode[]>(() =>
    applySelectionFlags(
      graphToReactFlow(graph).nodes,
      graphToReactFlow(graph).edges,
      selection
    ).nodes
  )
  const [edges, setEdges] = useState<Edge[]>(() =>
    applySelectionFlags(
      graphToReactFlow(graph).nodes,
      graphToReactFlow(graph).edges,
      selection
    ).edges
  )
  const nodesRef = useRef(nodes)
  const edgesRef = useRef(edges)
  const graphRef = useRef(graph)
  const selectionRef = useRef(selection)
  nodesRef.current = nodes
  edgesRef.current = edges
  graphRef.current = graph
  selectionRef.current = selection

  // 规格图变更时同步数据，并恢复当前选中（避免右侧面板被清空）
  useEffect(() => {
    const raw = graphToReactFlow(graph)
    const next = applySelectionFlags(raw.nodes, raw.edges, selectionRef.current)
    setNodes(next.nodes)
    setEdges(next.edges)
  }, [graph.nodes, graph.edges, graph.entryNodeId])

  // 外部 selection 变化时只更新 selected 标记，不重建整图
  useEffect(() => {
    setNodes((prev) =>
      prev.map((n) => ({
        ...n,
        selected: selection?.kind === 'node' && selection.id === n.id,
      }))
    )
    setEdges((prev) =>
      prev.map((e) => ({
        ...e,
        selected: selection?.kind === 'edge' && selection.id === e.id,
      }))
    )
  }, [selection])

  const persist = useCallback(
    (nextNodes: WorkflowFlowNode[], nextEdges: Edge[]) => {
      onGraphChange(
        reactFlowToGraph(
          graphRef.current,
          nextNodes,
          nextEdges,
          graphRef.current.viewport
        )
      )
    },
    [onGraphChange]
  )

  const onNodesChange = useCallback(
    (changes: NodeChange<WorkflowFlowNode>[]) => {
      setNodes((prev) => {
        const next = applyNodeChanges(changes, prev)
        if (!readOnly) {
          const shouldPersist = changes.some(
            (c) =>
              c.type === 'remove' ||
              c.type === 'add' ||
              (c.type === 'position' && c.dragging === false)
          )
          if (shouldPersist) {
            queueMicrotask(() => persist(next, edgesRef.current))
          }
        }
        return next
      })
    },
    [persist, readOnly]
  )

  const onEdgesChange = useCallback(
    (changes: EdgeChange<Edge>[]) => {
      setEdges((prev) => {
        const next = applyEdgeChanges(changes, prev)
        if (!readOnly) {
          const shouldPersist = changes.some(
            (c) => c.type === 'remove' || c.type === 'add'
          )
          if (shouldPersist) {
            queueMicrotask(() => persist(nodesRef.current, next))
          }
        }
        return next
      })
    },
    [persist, readOnly]
  )

  const onConnect = useCallback(
    (connection: Connection) => {
      if (readOnly) return
      const id = `e_${connection.source}_${connection.target}_${Date.now().toString(36)}`
      const data: WorkflowFlowEdgeData = {
        priority: 50,
        when: { type: 'always' },
        label: '新连接',
      }
      setEdges((prev) => {
        const next = addEdge(
          {
            ...connection,
            id,
            animated: true,
            label: formatEdgeCondition(data.when),
            data,
          },
          prev
        )
        queueMicrotask(() => persist(nodesRef.current, next))
        return next
      })
    },
    [persist, readOnly]
  )

  const handleSelectionChange = useCallback(
    ({ nodes: selectedNodes, edges: selectedEdges }: OnSelectionChangeParams) => {
      if (selectedNodes[0]) {
        onSelectionChange({ kind: 'node', id: selectedNodes[0].id })
        return
      }
      if (selectedEdges[0]) {
        onSelectionChange({ kind: 'edge', id: selectedEdges[0].id })
      }
      // 不同步空选中：图数据刷新会瞬时清空 RF selection
    },
    [onSelectionChange]
  )

  return (
    <div className='h-[min(720px,calc(100vh-240px))] min-h-[520px] w-full overflow-hidden rounded-xl border bg-[#f7f8fa]'>
      <ReactFlow
        className='h-full w-full'
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        nodesDraggable={!readOnly}
        nodesConnectable={!readOnly}
        elementsSelectable
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onSelectionChange={handleSelectionChange}
        onPaneClick={() => onSelectionChange(null)}
        onMoveEnd={(_, viewport) => {
          if (!readOnly) {
            onGraphChange({ ...graphRef.current, viewport })
          }
        }}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.2}
        maxZoom={1.5}
      >
        <Background gap={20} size={1} color='#d4d4d8' />
        <Controls showInteractive={!readOnly} />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  )
}

export function WorkflowCanvas(props: WorkflowCanvasProps) {
  return (
    <ReactFlowProvider>
      <WorkflowCanvasInner {...props} />
    </ReactFlowProvider>
  )
}
