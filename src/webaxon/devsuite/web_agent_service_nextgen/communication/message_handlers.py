"""Control message processing and dispatch for web agent service.

This module handles different types of control messages from the debugger:
- sync_active_sessions: Synchronize list of active sessions
- sync_session_agent: Update agent type for a session
- sync_session_template_version: Update template version for a session
- agent_control: Execute control commands (stop, pause, continue, step)
- run_meta_agent: Trigger the meta agent pipeline (trace collection + synthesis)

All handlers coordinate with SessionManager and AgentFactory to maintain
consistent state between the debugger and service.
"""
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any

from rich_python_utils.common_objects.debuggable import EXCEPTION_LOG_ITEM_KEY
from rich_python_utils.datetime_utils.common import timestamp

from webaxon.devsuite.common import DebuggerLogTypes
from ..core.config import ServiceConfig

logger = logging.getLogger(__name__)


class MessageHandlers:
    """Handles different types of control messages.
    
    This class processes control messages from the debugger and coordinates
    with other service components to execute the requested operations.
    
    Message handlers follow a consistent pattern:
    1. Extract required fields from message
    2. Validate message format
    3. Execute operation using injected dependencies
    4. Send response to control queue
    5. Log operation
    
    All responses include a timestamp and follow the message format
    specification from the design document.
    """
    
    def __init__(
        self,
        session_manager,
        agent_factory,
        queue_service,
        config: ServiceConfig,
        debugger=None
    ):
        """Initialize message handlers.

        Args:
            session_manager: SessionManager instance for session operations
            agent_factory: AgentFactory instance for agent creation
            queue_service: Queue service for sending responses
            config: Service configuration
            debugger: Debuggable instance for structured error logging
        """
        self._session_manager = session_manager
        self._agent_factory = agent_factory
        self._queue_service = queue_service
        self._config = config
        self._debugger = debugger
        self._debug_sessions: Dict[str, Any] = {}
        self._debug_sessions_lock = threading.Lock()
    
    def handle_sync_active_sessions(self, message: Dict[str, Any]) -> None:
        """Handle sync_active_sessions message.

        This message contains a list of all active session IDs from the debugger.
        The service uses this to:
        1. Limit sessions in debug mode (FIX 4)
        2. Create new sessions for unknown IDs (FIX 5)
        3. Clean up sessions no longer active (FIX 3)

        Message format:
        {
            'type': 'sync_active_sessions',
            'message': {
                'active_sessions': ['session1', 'session2', ...]
            },
            'timestamp': '...'
        }

        Response format:
        {
            'type': 'sync_active_sessions_response',
            'active_sessions': ['session1', 'session2', ...],
            'timestamp': '...'
        }

        Args:
            message: Message dictionary from control queue
        """
        # Extract active sessions from message
        payload = message.get('message', {})
        active_sessions = payload.get('active_sessions', [])

        # FIX 4: In synchronous debug mode, only allow ONE session
        if self._config.synchronous_agent and len(active_sessions) > 1:
            allowed_session = active_sessions[0]
            rejected_sessions = active_sessions[1:]

            for session_id in rejected_sessions:
                rejection_message = {
                    "type": "agent_status",
                    "message": {
                        "session_id": session_id,
                        "status": "rejected",
                        "error": "Synchronous agent mode allows only one session"
                    },
                    "timestamp": timestamp()
                }
                self._queue_service.put(self._config.client_control_queue_id, rejection_message)

            active_sessions = [allowed_session]

        # FIX 5: Create sessions for new session IDs
        current_sessions = self._session_manager.get_all_sessions()
        for session_id in active_sessions:
            if session_id not in current_sessions:
                try:
                    self._session_manager.get_or_create(
                        session_id=session_id,
                        agent_type=self._config.default_agent_type,
                        create_immediately=False
                    )
                    ack_message = {
                        "type": "agent_status",
                        "message": {
                            "session_id": session_id,
                            "status": "created",
                            "agent_type": self._config.default_agent_type
                        },
                        "timestamp": timestamp()
                    }
                    self._queue_service.put(self._config.client_control_queue_id, ack_message)
                except Exception as e:
                    error_ack = {
                        "type": "agent_status",
                        "message": {
                            "session_id": session_id,
                            "status": "error",
                            "error": str(e)
                        },
                        "timestamp": timestamp()
                    }
                    self._queue_service.put(self._config.client_control_queue_id, error_ack)
            else:
                # Update last_active for existing sessions
                self._session_manager.update_session(session_id)

        # FIX 3: Clean up sessions not in active_sessions
        current_session_ids = list(self._session_manager.get_all_sessions().keys())
        sessions_to_remove = [sid for sid in current_session_ids if sid not in active_sessions]
        for session_id in sessions_to_remove:
            try:
                self._session_manager.cleanup_session(session_id)
            except Exception as e:
                self._debugger.log_error({
                    EXCEPTION_LOG_ITEM_KEY: e,
                    'session_id': session_id,
                })

        # Send response with updated session list
        updated_sessions = list(self._session_manager.get_all_sessions().keys())
        response = {
            'type': 'sync_active_sessions_response',
            'active_sessions': updated_sessions,
            'timestamp': timestamp()
        }

        self._queue_service.put(self._config.client_control_queue_id, response)
    
    def handle_sync_session_agent(self, message: Dict[str, Any]) -> None:
        """Handle sync_session_agent message.
        
        This message updates the agent type for a specific session.
        If the agent hasn't been created yet, this updates the session's
        agent_type field. If the agent is already created, the change is rejected.
        
        Message format:
        {
            'type': 'sync_session_agent',
            'message': {
                'session_id': 'session1',
                'agent_type': 'DefaultAgent'
            },
            'timestamp': '...'
        }
        
        Response format:
        {
            'type': 'sync_session_agent_response',
            'session_id': 'session1',
            'agent_type': 'DefaultAgent',
            'agent_status': 'not_created' | 'created' | 'running' | 'error',
            'agent_created': True | False,
            'timestamp': '...'
        }
        
        Args:
            message: Message dictionary from control queue
        """
        # Extract session_id and agent_type from message
        payload = message.get('message', {})
        session_id = payload.get('session_id')
        agent_type = payload.get('agent_type')
        
        if not session_id:
            response = {
                'type': 'sync_session_agent_response',
                'error': 'Missing required field: session_id',
                'timestamp': timestamp()
            }
            self._queue_service.put(self._config.client_control_queue_id, response)
            return

        # Get or create session
        session = self._session_manager.get_or_create(
            session_id=session_id,
            agent_type=agent_type,
            create_immediately=False
        )

        # Update agent type if agent not yet created
        if not session.info.initialized and agent_type:
            self._session_manager.update_session(
                session_id=session_id,
                session_type=agent_type
            )

        # Determine agent status
        if session.agent is None:
            agent_status = 'not_created'
        elif session.agent_thread and session.agent_thread.is_alive():
            agent_status = 'running'
        elif session.info.last_agent_status:
            agent_status = session.info.last_agent_status
        else:
            agent_status = 'created'

        # Send response
        response = {
            'type': 'sync_session_agent_response',
            'session_id': session_id,
            'agent_type': session.info.session_type,
            'agent_status': agent_status,
            'agent_created': session.info.initialized,
            'timestamp': timestamp()
        }

        self._queue_service.put(self._config.client_control_queue_id, response)
    
    def handle_sync_session_template_version(self, message: Dict[str, Any]) -> None:
        """Handle sync_session_template_version message.

        This message updates the template version for a specific session.
        The template version is stored in the session and will be used
        when the agent is created.

        Message format:
        {
            'type': 'sync_session_template_version',
            'message': {
                'session_id': 'session1',
                'template_version': 'v2.1'
            },
            'timestamp': '...'
        }

        Response format:
        {
            'type': 'sync_session_template_version_response',
            'session_id': 'session1',
            'template_version': 'v2.1',
            'timestamp': '...'
        }

        Args:
            message: Message dictionary from control queue
        """
        # Extract session_id and template_version from message
        payload = message.get('message', {})
        session_id = payload.get('session_id')
        template_version = payload.get('template_version', '')

        if not session_id:
            response = {
                'type': 'sync_session_template_version_response',
                'error': 'Missing required field: session_id',
                'timestamp': timestamp()
            }
            self._queue_service.put(self._config.client_control_queue_id, response)
            return

        # Get or create session
        session = self._session_manager.get_or_create(
            session_id=session_id,
            create_immediately=False
        )

        # Update template version
        self._session_manager.update_session(
            session_id=session_id,
            template_version=template_version
        )

        # Send response
        response = {
            'type': 'sync_session_template_version_response',
            'session_id': session_id,
            'template_version': session.info.template_version,
            'timestamp': timestamp()
        }

        self._queue_service.put(self._config.client_control_queue_id, response)
    
    def handle_agent_control(self, message: Dict[str, Any]) -> None:
        """Handle agent_control message (stop/pause/continue/step).

        This message executes a control command on an agent's workflow.
        The control is applied directly to the agent instance.

        Message format:
        {
            'type': 'agent_control',
            'message': {
                'session_id': 'session1',
                'control': 'pause'  # or 'continue', 'stop', 'step'
            },
            'timestamp': '...'
        }

        Response format:
        {
            'type': 'agent_control_ack',
            'session_id': 'session1',
            'control': 'pause',
            'success': True | False,
            'timestamp': '...'
        }

        Args:
            message: Message dictionary from control queue
        """
        # Extract session_id and control command from message
        payload = message.get('message', {})
        session_id = payload.get('session_id')
        control = payload.get('control')

        if not session_id or not control:
            # Invalid message - missing required fields
            return

        # Get session
        session = self._session_manager.get(session_id)

        success = False
        if session and session.interactive:
            # Apply control to interactive interface
            try:
                if control == 'stop':
                    session.interactive.stop()
                    success = True
                elif control == 'pause':
                    session.interactive.pause()
                    success = True
                elif control == 'continue':
                    session.interactive.resume()
                    success = True
                elif control == 'step':
                    session.interactive.step()
                    success = True
            except Exception as e:
                # Log error but don't crash
                session.log_error({
                    'type': 'AGENT_CONTROL_ERROR',
                    'message': f'Error applying control {control}: {e}',
                    'session_id': session_id,
                    'control': control
                })

        # Send acknowledgment
        response = {
            'type': 'agent_control_ack',
            'session_id': session_id,
            'control': control,
            'success': success,
            'timestamp': timestamp()
        }

        self._queue_service.put(self._config.client_control_queue_id, response)
    
    def handle_register_knowledge(self, message: Dict[str, Any]) -> None:
        """Handle register_knowledge message.

        Sends free-text to the LLM via KnowledgeIngestionCLI which structurizes
        it into metadata, classified knowledge pieces, and graph relationships,
        then loads everything into the KnowledgeBase.

        Message format:
        {
            'type': 'register_knowledge',
            'message': {
                'content': 'Name: Tony Chen ...'
            },
            'timestamp': '...'
        }

        Args:
            message: Message dictionary from control queue
        """
        payload = message.get('message', {})
        content = payload.get('content')

        if not content:
            response = {
                'type': 'register_knowledge_response',
                'success': False,
                'counts': None,
                'message': 'Missing required field: content',
                'timestamp': timestamp()
            }
            self._queue_service.put(self._config.client_control_queue_id, response)
            return

        try:
            counts = self._agent_factory.ingest_knowledge(user_text=content)
            response = {
                'type': 'register_knowledge_response',
                'success': True,
                'counts': counts,
                'message': 'Knowledge ingested via LLM structuring',
                'timestamp': timestamp()
            }
        except Exception as e:
            response = {
                'type': 'register_knowledge_response',
                'success': False,
                'counts': None,
                'message': f'Error: {e}',
                'timestamp': timestamp()
            }

        self._queue_service.put(self._config.client_control_queue_id, response)

    def handle_kb_add(self, message: Dict[str, Any]) -> None:
        """Handle kb_add message.

        Ingests free text via DocumentIngester.ingest_text() which chunks,
        LLM-structures, and loads into the KnowledgeBase.

        Args:
            message: Message dictionary from control queue
        """
        payload = message.get('message', {})
        text = payload.get('text')

        if not text:
            response = {
                'type': 'kb_add_response',
                'success': False,
                'message': 'Missing required field: text',
                'timestamp': timestamp()
            }
            self._queue_service.put(self._config.client_control_queue_id, response)
            return

        spaces = payload.get('spaces')

        ingester = self._agent_factory.get_document_ingester()
        kb = self._agent_factory.get_knowledge_base()
        result = ingester.ingest_text(text, kb, spaces=spaces)

        if not result.success:
            response = {
                'type': 'kb_add_response',
                'success': False,
                'message': f'Ingestion failed: {", ".join(str(e) for e in result.errors)}',
                'timestamp': timestamp()
            }
        else:
            response = {
                'type': 'kb_add_response',
                'success': True,
                'counts': {
                    'pieces_created': result.pieces_created,
                    'metadata_created': result.metadata_created,
                    'graph_nodes_created': result.graph_nodes_created,
                    'graph_edges_created': result.graph_edges_created,
                },
                'message': 'Knowledge ingested via LLM structuring',
                'timestamp': timestamp()
            }

        self._queue_service.put(self._config.client_control_queue_id, response)

    def handle_kb_update(self, message: Dict[str, Any]) -> None:
        """Handle kb_update message.

        Updates knowledge via KnowledgeUpdater.update_by_content() which
        semantically searches for similar pieces and applies LLM-analyzed updates.

        Args:
            message: Message dictionary from control queue
        """
        payload = message.get('message', {})
        text = payload.get('text')

        if not text:
            response = {
                'type': 'kb_update_response',
                'success': False,
                'message': 'Missing required field: text',
                'timestamp': timestamp()
            }
            self._queue_service.put(self._config.client_control_queue_id, response)
            return

        updater = self._agent_factory.get_knowledge_updater()
        results = updater.update_by_content(text, update_instruction=text)

        if not results:
            response = {
                'type': 'kb_update_response',
                'success': True,
                'results': [],
                'count': 0,
                'message': 'No pieces were updated',
                'timestamp': timestamp()
            }
        else:
            successes = [r for r in results if r.success]
            failures = [r for r in results if not r.success]

            serialized = [
                {
                    'piece_id': r.piece_id,
                    'old_version': r.old_version,
                    'new_version': r.new_version,
                    'action': r.details.get("action", r.operation),
                }
                for r in successes
            ]

            if serialized:
                msg = f'Updated {len(serialized)} piece{"s" if len(serialized) != 1 else ""}'
            elif failures:
                msg = f'{len(failures)} update{"s" if len(failures) != 1 else ""} failed'
            else:
                msg = 'No matching pieces found'

            response = {
                'type': 'kb_update_response',
                'success': len(successes) > 0,
                'results': serialized,
                'count': len(serialized),
                'message': msg,
                'errors': [r.error for r in failures] if failures else [],
                'timestamp': timestamp()
            }

        self._queue_service.put(self._config.client_control_queue_id, response)

    def handle_kb_del(self, message: Dict[str, Any]) -> None:
        """Handle kb_del message.

        Supports three phases:
        - "search": semantic search for candidates, raises ConfirmationRequiredError
        - "confirm": delete confirmed piece_ids
        - "direct": delete a single piece by ID

        Args:
            message: Message dictionary from control queue
        """
        from agent_foundation.knowledge.ingestion.knowledge_deleter import (
            ConfirmationRequiredError,
            DeleteMode,
        )

        payload = message.get('message', {})
        phase = payload.get('phase', 'search')
        deleter = self._agent_factory.get_knowledge_deleter()

        if phase == 'search':
            query = payload.get('query', '')
            try:
                deleter.delete_by_query(query)
                # If no ConfirmationRequiredError, no candidates matched
                response = {
                    'type': 'kb_del_response',
                    'success': True,
                    'phase': 'candidates',
                    'candidates': [],
                    'count': 0,
                    'timestamp': timestamp()
                }
            except ConfirmationRequiredError as e:
                from webaxon.devsuite.web_agent_service_nextgen.cli.kb_formatters import truncate_content
                candidates = [
                    {
                        'piece_id': piece.piece_id,
                        'content_preview': truncate_content(piece.content),
                        'score': score,
                    }
                    for piece, score in e.candidates
                ]
                response = {
                    'type': 'kb_del_response',
                    'success': True,
                    'phase': 'candidates',
                    'candidates': candidates,
                    'count': len(candidates),
                    'timestamp': timestamp()
                }

        elif phase == 'confirm':
            query = payload.get('query', '')
            confirmed_ids = payload.get('piece_ids', [])
            results = deleter.delete_by_query(query, piece_ids=confirmed_ids)
            serialized = [
                {
                    'piece_id': r.piece_id,
                    'success': r.success,
                    'message': r.error,
                }
                for r in results
            ]
            response = {
                'type': 'kb_del_response',
                'success': True,
                'phase': 'done',
                'results': serialized,
                'mode': 'soft',
                'count': len(serialized),
                'timestamp': timestamp()
            }

        elif phase == 'direct':
            piece_id = payload.get('piece_id', '')
            hard = payload.get('hard', False)
            mode = DeleteMode.HARD if hard else DeleteMode.SOFT
            result = deleter.delete_by_id(piece_id, mode)
            response = {
                'type': 'kb_del_response',
                'success': result.success,
                'phase': 'done',
                'results': [
                    {
                        'piece_id': result.piece_id,
                        'success': result.success,
                        'message': result.error,
                    }
                ],
                'mode': 'hard' if hard else 'soft',
                'count': 1 if result.success else 0,
                'timestamp': timestamp()
            }

        else:
            response = {
                'type': 'kb_del_response',
                'success': False,
                'message': f'Unknown phase: {phase}',
                'timestamp': timestamp()
            }

        self._queue_service.put(self._config.client_control_queue_id, response)

    def handle_kb_get(self, message: Dict[str, Any]) -> None:
        """Handle kb_get message.

        Searches the knowledge base via KnowledgeBase.retrieve() and returns
        matching pieces with relevance scores.

        Args:
            message: Message dictionary from control queue
        """
        from webaxon.devsuite.web_agent_service_nextgen.cli.kb_formatters import truncate_content

        payload = message.get('message', {})
        query = payload.get('query', '')
        domain = payload.get('domain')
        limit = payload.get('limit', 5)
        entity_id = payload.get('entity_id')
        tags = payload.get('tags')
        spaces = payload.get('spaces')

        kb = self._agent_factory.get_knowledge_base()
        retrieval_result = kb.retrieve(
            query, domain=domain, top_k=limit, entity_id=entity_id, tags=tags,
            spaces=spaces,
        )

        results = [
            {
                'piece_id': piece.piece_id,
                'content': truncate_content(piece.content),
                'domain': piece.domain,
                'tags': piece.tags,
                'knowledge_type': piece.knowledge_type,
                'score': score,
            }
            for piece, score in retrieval_result.pieces
        ]

        response = {
            'type': 'kb_get_response',
            'success': True,
            'results': results,
            'count': len(results),
            'timestamp': timestamp()
        }

        self._queue_service.put(self._config.client_control_queue_id, response)

    def handle_kb_list(self, message: Dict[str, Any]) -> None:
        """Handle kb_list message.

        Lists knowledge pieces from the piece store, optionally filtered
        by entity_id and domain.

        Args:
            message: Message dictionary from control queue
        """
        from webaxon.devsuite.web_agent_service_nextgen.cli.kb_formatters import truncate_content

        payload = message.get('message', {})
        entity_id = payload.get('entity_id')
        domain = payload.get('domain')
        spaces = payload.get('spaces')

        kb = self._agent_factory.get_knowledge_base()
        pieces = kb.piece_store.list_all(entity_id=entity_id, spaces=spaces)

        if domain:
            pieces = [p for p in pieces if p.domain == domain]

        results = [
            {
                'piece_id': p.piece_id,
                'content': truncate_content(p.content),
                'domain': p.domain,
                'tags': p.tags,
                'knowledge_type': p.knowledge_type,
                'is_active': p.is_active,
            }
            for p in pieces
        ]

        response = {
            'type': 'kb_list_response',
            'success': True,
            'results': results,
            'count': len(results),
            'timestamp': timestamp()
        }

        self._queue_service.put(self._config.client_control_queue_id, response)

    def handle_kb_restore(self, message: Dict[str, Any]) -> None:
        """Handle kb_restore message.

        Restores a soft-deleted knowledge piece via KnowledgeDeleter.restore_by_id().

        Args:
            message: Message dictionary from control queue
        """
        payload = message.get('message', {})
        piece_id = payload.get('piece_id')

        if not piece_id:
            response = {
                'type': 'kb_restore_response',
                'success': False,
                'message': 'Missing required field: piece_id',
                'timestamp': timestamp()
            }
            self._queue_service.put(self._config.client_control_queue_id, response)
            return

        deleter = self._agent_factory.get_knowledge_deleter()
        result = deleter.restore_by_id(piece_id)

        if result.success:
            response = {
                'type': 'kb_restore_response',
                'success': True,
                'piece_id': result.piece_id,
                'message': f'Restored piece: {result.piece_id}',
                'timestamp': timestamp()
            }
        else:
            response = {
                'type': 'kb_restore_response',
                'success': False,
                'message': result.error,
                'timestamp': timestamp()
            }

        self._queue_service.put(self._config.client_control_queue_id, response)

    def handle_kb_review_spaces(self, message: Dict[str, Any]) -> None:
        """Handle kb_review_spaces message.

        Supports three modes:
        - list: return all pieces with space_suggestion_status == "pending"
        - approve: apply pending suggestions to spaces, clear suggestion fields
        - reject: clear suggestion fields without modifying spaces

        Args:
            message: Message dictionary from control queue
        """
        from webaxon.devsuite.web_agent_service_nextgen.cli.kb_formatters import truncate_content

        payload = message.get('message', {})
        mode = payload.get('mode', 'list')
        piece_id = payload.get('piece_id')

        kb = self._agent_factory.get_knowledge_base()

        if mode == 'list':
            all_pieces = kb.piece_store.list_all()
            pending = [
                p for p in all_pieces
                if getattr(p, 'space_suggestion_status', None) == 'pending'
            ]
            results = [
                {
                    'piece_id': p.piece_id,
                    'summary': getattr(p, 'summary', None),
                    'content': truncate_content(p.content, 100),
                    'current_spaces': list(p.spaces),
                    'suggested_spaces': list(p.pending_space_suggestions or []),
                    'reasons': list(p.space_suggestion_reasons or []),
                }
                for p in pending
            ]
            response = {
                'type': 'kb_review_spaces_response',
                'success': True,
                'results': results,
                'count': len(results),
                'timestamp': timestamp(),
            }

        elif mode == 'approve':
            if not piece_id:
                response = {
                    'type': 'kb_review_spaces_response',
                    'success': False,
                    'message': 'Missing required field: piece_id',
                    'timestamp': timestamp(),
                }
                self._queue_service.put(self._config.client_control_queue_id, response)
                return

            piece = kb.piece_store.get_by_id(piece_id)
            if piece is None:
                response = {
                    'type': 'kb_review_spaces_response',
                    'success': False,
                    'message': f'Piece not found: {piece_id}',
                    'timestamp': timestamp(),
                }
                self._queue_service.put(self._config.client_control_queue_id, response)
                return

            # Merge pending suggestions into spaces (deduplicate, preserve order)
            merged = list(piece.spaces)
            for s in (piece.pending_space_suggestions or []):
                if s not in merged:
                    merged.append(s)
            piece.spaces = merged
            piece.space = piece.spaces[0]
            piece.pending_space_suggestions = None
            piece.space_suggestion_reasons = None
            piece.space_suggestion_status = "approved"

            kb.piece_store.update(piece)

            response = {
                'type': 'kb_review_spaces_response',
                'success': True,
                'message': f'Approved suggestions for piece {piece_id}. Spaces: {piece.spaces}',
                'piece_id': piece_id,
                'spaces': list(piece.spaces),
                'timestamp': timestamp(),
            }

        elif mode == 'reject':
            if not piece_id:
                response = {
                    'type': 'kb_review_spaces_response',
                    'success': False,
                    'message': 'Missing required field: piece_id',
                    'timestamp': timestamp(),
                }
                self._queue_service.put(self._config.client_control_queue_id, response)
                return

            piece = kb.piece_store.get_by_id(piece_id)
            if piece is None:
                response = {
                    'type': 'kb_review_spaces_response',
                    'success': False,
                    'message': f'Piece not found: {piece_id}',
                    'timestamp': timestamp(),
                }
                self._queue_service.put(self._config.client_control_queue_id, response)
                return

            # Clear suggestion fields without modifying spaces
            piece.pending_space_suggestions = None
            piece.space_suggestion_reasons = None
            piece.space_suggestion_status = "rejected"

            kb.piece_store.update(piece)

            response = {
                'type': 'kb_review_spaces_response',
                'success': True,
                'message': f'Rejected suggestions for piece {piece_id}. Spaces unchanged: {piece.spaces}',
                'piece_id': piece_id,
                'spaces': list(piece.spaces),
                'timestamp': timestamp(),
            }

        else:
            response = {
                'type': 'kb_review_spaces_response',
                'success': False,
                'message': f'Unknown mode: {mode}',
                'timestamp': timestamp(),
            }

        self._queue_service.put(self._config.client_control_queue_id, response)

    def handle_set_browser_profile(self, message: Dict[str, Any]) -> None:
        """Handle set_browser_profile message.

        Updates the service config with the requested Chrome profile settings
        before an agent (and its WebDriver) is created.

        Message format:
        {
            'type': 'set_browser_profile',
            'message': {
                'profile_directory': 'Profile 1',
                'user_data_dir': '/path/to/chrome/user-data'  (optional)
            },
            'timestamp': '...'
        }
        """
        payload = message.get('message', {})
        profile_directory = payload.get('profile_directory')
        user_data_dir = payload.get('user_data_dir')
        copy_profile = payload.get('copy_profile')

        if profile_directory:
            self._config.chrome_profile_directory = profile_directory
        if user_data_dir:
            self._config.chrome_user_data_dir = user_data_dir
        if copy_profile is not None:
            self._config.chrome_copy_profile = bool(copy_profile)

        logger.info(
            "Browser profile updated: profile_directory=%s, user_data_dir=%s, copy_profile=%s",
            self._config.chrome_profile_directory,
            self._config.chrome_user_data_dir,
            self._config.chrome_copy_profile,
        )

        response = {
            'type': 'set_browser_profile_response',
            'success': True,
            'profile_directory': self._config.chrome_profile_directory,
            'user_data_dir': self._config.chrome_user_data_dir,
            'copy_profile': self._config.chrome_copy_profile,
            'timestamp': timestamp(),
        }
        self._queue_service.put(self._config.client_control_queue_id, response)

    def dispatch(self, message: Dict[str, Any]) -> None:
        """Dispatch message to appropriate handler.
        
        This method routes incoming control messages to the correct handler
        based on the message type. Unknown message types are logged but
        don't cause errors.
        
        Args:
            message: Message dictionary from control queue
        """
        if not isinstance(message, dict):
            # Invalid message format
            return
        
        message_type = message.get('type')
        
        # Map message types to handlers
        handlers = {
            'sync_active_sessions': self.handle_sync_active_sessions,
            'sync_session_agent': self.handle_sync_session_agent,
            'sync_session_template_version': self.handle_sync_session_template_version,
            'agent_control': self.handle_agent_control,
            'register_knowledge': self.handle_register_knowledge,
            'run_meta_agent': self.handle_run_meta_agent,
            'meta_debug_command': self.handle_meta_debug_command,
            'kb_add': self.handle_kb_add,
            'kb_update': self.handle_kb_update,
            'kb_del': self.handle_kb_del,
            'kb_get': self.handle_kb_get,
            'kb_list': self.handle_kb_list,
            'kb_restore': self.handle_kb_restore,
            'kb_review_spaces': self.handle_kb_review_spaces,
            'set_browser_profile': self.handle_set_browser_profile,
        }
        
        # Get handler for this message type
        handler = handlers.get(message_type)
        
        if handler:
            try:
                handler(message)
            except Exception as e:
                self._debugger.log_error({
                    EXCEPTION_LOG_ITEM_KEY: e,
                    'message_type': message_type,
                })
                # Send error response so the client doesn't hang waiting
                error_response = {
                    'type': f'{message_type}_response',
                    'success': False,
                    'message': str(e),
                    'error': str(e),
                    'timestamp': timestamp(),
                }
                try:
                    self._queue_service.put(
                        self._config.client_control_queue_id, error_response
                    )
                except Exception:
                    pass
        else:
            self._debugger.log_warning({
                'type': DebuggerLogTypes.CONTROL_MESSAGE,
                'message': f'Unknown message type: {message_type}',
                'message_type': message_type,
            })

    # ------------------------------------------------------------------
    # Meta Agent Pipeline
    # ------------------------------------------------------------------

    def handle_run_meta_agent(self, message: Dict[str, Any]) -> None:
        """Handle run_meta_agent message.

        Spawns a background thread to run the full meta agent pipeline.
        Sends immediate "started" acknowledgment, progress updates per
        agent run, and a final result with output path.

        When ``debug`` is True in the payload, the pipeline runs
        synchronously in the calling thread (blocking the control loop)
        so a debugger can step through each agent run.

        Message format::

            {
                'type': 'run_meta_agent',
                'message': {
                    'query': 'Navigate to login page and log in',
                    'run_count': 5,              # optional, default 5
                    'synthesis_strategy': '...',  # optional
                    'evaluation_strategy': '...', # optional
                    'validate': False,            # optional
                    'debug': False,              # optional, run synchronously
                },
                'timestamp': '...'
            }
        """
        payload = message.get('message', {})
        query = payload.get('query')

        if not query:
            response = {
                'type': 'run_meta_agent_response',
                'success': False,
                'error': 'Missing required field: query',
                'timestamp': timestamp(),
            }
            self._queue_service.put(
                self._config.client_control_queue_id, response
            )
            return

        run_count = payload.get('run_count', 5)
        synthesis_strategy = payload.get('synthesis_strategy', 'rule_based')
        evaluation_strategy = payload.get(
            'evaluation_strategy', 'exception_only'
        )
        validate = payload.get('validate', False)
        debug = payload.get('debug', False)

        # Send immediate acknowledgment
        started_msg = {
            'type': 'run_meta_agent_started',
            'message': 'Meta agent pipeline started',
            'run_count': run_count,
            'debug': debug,
            'timestamp': timestamp(),
        }
        self._queue_service.put(
            self._config.client_control_queue_id, started_msg
        )

        pipeline_args = (
            query,
            run_count,
            synthesis_strategy,
            evaluation_strategy,
            validate,
        )

        if debug:
            # Run synchronously — blocks the control loop but allows
            # stepping through with a debugger.
            logger.info("Meta agent pipeline running in DEBUG (synchronous) mode")
            self._run_meta_agent_pipeline(*pipeline_args)
        else:
            # Spawn background thread
            thread = threading.Thread(
                target=self._run_meta_agent_pipeline,
                args=pipeline_args,
                daemon=True,
                name='MetaAgentPipeline',
            )
            thread.start()

    def _run_meta_agent_pipeline(
        self,
        query: str,
        run_count: int,
        synthesis_strategy: str,
        evaluation_strategy: str,
        validate: bool,
        pipeline_dir: Path = None,
        pipeline_session_id: str = None,
        stage_hook=None,
    ) -> None:
        """Run the meta agent pipeline in a background thread.

        Parameters
        ----------
        pipeline_dir:
            If provided, use this directory for staged output.
            If ``None``, a new directory is created under ``_runtime/meta_agent/``.
        pipeline_session_id:
            If provided, use this as the session ID for output paths.
            If ``None``, one is generated as ``meta_<timestamp>``.
        stage_hook:
            Optional callback passed to the pipeline.  Used by debug mode
            to block between stages.
        """
        from agent_foundation.automation.meta_agent.models import (
            PipelineConfig,
        )

        from webaxon.automation.meta_agent.web_pipeline import (
            create_web_meta_agent_pipeline,
        )

        from ..agents.meta_agent_adapter import MetaAgentAdapter

        try:
            # Resolve output directory
            output_dir = (
                self._agent_factory._testcase_root / '_runtime' / 'meta_agent'
            )
            output_dir.mkdir(parents=True, exist_ok=True)

            if pipeline_dir is None:
                ts = timestamp().replace(' ', '_').replace(':', '')
                if pipeline_session_id is None:
                    pipeline_session_id = f"meta_{ts}"
                pipeline_dir = output_dir / pipeline_session_id
                pipeline_dir.mkdir(parents=True, exist_ok=True)

            # Write manifest
            manifest = {
                "session_id": pipeline_session_id,
                "query": query,
                "mode": "debug" if stage_hook else "normal",
                "created_at": timestamp(),
                "config": {
                    "run_count": run_count,
                    "synthesis_strategy": synthesis_strategy,
                    "evaluation_strategy": evaluation_strategy,
                    "validate": validate,
                },
                "completed_stages": [],
            }
            (pipeline_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2)
            )

            # Progress callback: sends updates to CLI
            def on_progress(current_run: int, total_runs: int) -> None:
                progress_msg = {
                    'type': 'run_meta_agent_progress',
                    'message': f'Agent run {current_run}/{run_count} completed',
                    'current_run': current_run,
                    'total_runs': run_count,
                    'pipeline_session_id': pipeline_session_id,
                    'timestamp': timestamp(),
                }
                self._queue_service.put(
                    self._config.client_control_queue_id, progress_msg
                )

            # Agent output callback: forwards each agent response to CLI
            def on_agent_output(current_run: int, response: dict) -> None:
                text = response.get("response", "")
                output_msg = {
                    'type': 'run_meta_agent_agent_output',
                    'current_run': current_run,
                    'total_runs': run_count,
                    'agent_response': str(text) if text else "",
                    'flag': str(response.get("flag", "")),
                    'pipeline_session_id': pipeline_session_id,
                    'timestamp': timestamp(),
                }
                self._queue_service.put(
                    self._config.client_control_queue_id, output_msg
                )

            # Create adapter
            adapter = MetaAgentAdapter(
                agent_factory=self._agent_factory,
                session_manager=self._session_manager,
                queue_service=self._queue_service,
                config=self._config,
                progress_callback=on_progress,
                agent_output_callback=on_agent_output,
                pipeline_dir=pipeline_dir,
            )

            # Build pipeline config
            config = PipelineConfig(
                run_count=run_count,
                synthesis_strategy=synthesis_strategy,
                evaluation_strategy=evaluation_strategy,
                validate=validate,
            )

            # Create pipeline with web configuration
            pipeline = create_web_meta_agent_pipeline(
                agent=adapter,
                action_executor=None,
                config=config,
                output_dir=pipeline_dir,
                stage_hook=stage_hook,
            )

            # Run pipeline
            result = pipeline.run(query)

            # Write result inside pipeline session folder
            output_path = pipeline_dir / 'result.json'

            serialized = _serialize_pipeline_result(result)
            output_path.write_text(
                json.dumps(serialized, indent=2, default=str)
            )

            # Update manifest with completed stages
            try:
                completed_stages = []
                for stage_name in ("collection", "evaluation", "synthesis", "validation"):
                    cp = pipeline_dir / f"stage_{stage_name}" / "checkpoint.json"
                    if cp.exists():
                        completed_stages.append(stage_name)
                manifest["completed_stages"] = completed_stages
                (pipeline_dir / "manifest.json").write_text(
                    json.dumps(manifest, indent=2)
                )
            except Exception:
                logger.warning("Failed to update manifest", exc_info=True)

            # Build summary
            passed_count = 0
            if result.evaluation_results:
                passed_count = sum(
                    1 for r in result.evaluation_results if r.passed
                )

            summary = {
                'trace_count': len(result.traces),
                'passed_traces': passed_count,
                'failed_stage': result.failed_stage,
            }

            response = {
                'type': 'run_meta_agent_response',
                'success': result.failed_stage is None,
                'output_path': str(output_path),
                'summary': summary,
                'error': result.error,
                'pipeline_session_id': pipeline_session_id,
                'timestamp': timestamp(),
            }

        except Exception as e:
            logger.error("Meta agent pipeline error: %s", e, exc_info=True)
            response = {
                'type': 'run_meta_agent_response',
                'success': False,
                'error': f'Pipeline error: {e}',
                'output_path': None,
                'pipeline_session_id': pipeline_session_id,
                'timestamp': timestamp(),
            }

        self._queue_service.put(
            self._config.client_control_queue_id, response
        )

        # Debug mode cleanup: mark controller as done and remove from sessions
        if stage_hook is not None and pipeline_session_id is not None:
            with self._debug_sessions_lock:
                controller = self._debug_sessions.get(pipeline_session_id)
            if controller is not None:
                with controller._lock:
                    controller.pipeline_done = True
                with self._debug_sessions_lock:
                    self._debug_sessions.pop(pipeline_session_id, None)

    # ------------------------------------------------------------------
    # Meta Agent Debug Commands
    # ------------------------------------------------------------------

    def handle_meta_debug_command(self, message: Dict[str, Any]) -> None:
        """Dispatch meta debug subcommands."""
        payload = message.get('message', {})
        command = payload.get('command', '')

        if command == 'collect':
            self._handle_debug_collect(payload)
        elif command in ('evaluate', 'synthesize', 'validate'):
            self._handle_debug_advance(command, payload)
        elif command == 'status':
            self._handle_debug_status(payload)
        elif command == 'abort':
            self._handle_debug_abort(payload)
        else:
            self._queue_service.put(
                self._config.client_control_queue_id,
                {
                    'type': 'meta_debug_error',
                    'error': f'Unknown debug command: {command}',
                    'timestamp': timestamp(),
                },
            )

    def _handle_debug_collect(self, payload: dict) -> None:
        """Start a new debug session and run COLLECT."""
        from ..agents.stage_gate_controller import StageGateController

        query = payload.get('query', '')
        run_count = payload.get('run_count', 5)

        if not query:
            self._queue_service.put(
                self._config.client_control_queue_id,
                {
                    'type': 'meta_debug_error',
                    'error': 'Missing required field: query',
                    'timestamp': timestamp(),
                },
            )
            return

        # Enforce max concurrent sessions
        with self._debug_sessions_lock:
            if len(self._debug_sessions) >= 5:
                self._queue_service.put(
                    self._config.client_control_queue_id,
                    {
                        'type': 'meta_debug_error',
                        'error': 'Maximum concurrent debug sessions (5) reached',
                        'timestamp': timestamp(),
                    },
                )
                return

        # Generate session ID and pipeline directory
        ts = timestamp().replace(' ', '_').replace(':', '')
        session_id = f"meta_debug_{ts}"

        output_dir = (
            self._agent_factory._testcase_root / '_runtime' / 'meta_agent'
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        pipeline_dir = output_dir / session_id
        pipeline_dir.mkdir(parents=True, exist_ok=True)

        # Create controller
        controller = StageGateController(
            session_id=session_id,
            query=query,
            queue_service=self._queue_service,
            config=self._config,
            output_dir=pipeline_dir,
        )

        with self._debug_sessions_lock:
            self._debug_sessions[session_id] = controller

        # Send session created ack
        self._queue_service.put(
            self._config.client_control_queue_id,
            {
                'type': 'meta_debug_session_created',
                'session_id': session_id,
                'timestamp': timestamp(),
            },
        )

        # Start pipeline in background thread
        thread = threading.Thread(
            target=self._run_meta_agent_pipeline,
            args=(query, run_count, 'rule_based', 'exception_only', False),
            kwargs={
                'pipeline_dir': pipeline_dir,
                'pipeline_session_id': session_id,
                'stage_hook': controller.stage_hook,
            },
            daemon=True,
            name=f'MetaDebug-{session_id}',
        )
        thread.start()

    def _handle_debug_advance(self, command: str, payload: dict) -> None:
        """Resume the pipeline for a debug session (evaluate/synthesize/validate)."""
        session_id = payload.get('session_id', '')

        # Lookup under lock, then release BEFORE calling controller methods.
        # This prevents deadlock: service loop holds _debug_sessions_lock →
        # controller._lock, while pipeline thread holds controller._lock →
        # _debug_sessions_lock (during cleanup).
        with self._debug_sessions_lock:
            controller = self._debug_sessions.get(session_id)

        if controller is None:
            self._queue_service.put(
                self._config.client_control_queue_id,
                {
                    'type': 'meta_debug_error',
                    'error': f'Debug session not found: {session_id}',
                    'session_id': session_id,
                    'timestamp': timestamp(),
                },
            )
            return

        expected = controller.next_expected_command
        if expected != command:
            self._queue_service.put(
                self._config.client_control_queue_id,
                {
                    'type': 'meta_debug_error',
                    'error': f"Session expects '{expected}' next, not '{command}'",
                    'session_id': session_id,
                    'timestamp': timestamp(),
                },
            )
            return

        if not controller.resume():
            self._queue_service.put(
                self._config.client_control_queue_id,
                {
                    'type': 'meta_debug_error',
                    'error': 'Pipeline exited unexpectedly',
                    'session_id': session_id,
                    'timestamp': timestamp(),
                },
            )
            return

    def _handle_debug_abort(self, payload: dict) -> None:
        """Abort a debug session."""
        session_id = payload.get('session_id', '')

        with self._debug_sessions_lock:
            controller = self._debug_sessions.get(session_id)

        if controller is None:
            self._queue_service.put(
                self._config.client_control_queue_id,
                {
                    'type': 'meta_debug_error',
                    'error': f'Debug session not found: {session_id}',
                    'session_id': session_id,
                    'timestamp': timestamp(),
                },
            )
            return

        controller.abort()

    def _handle_debug_status(self, payload: dict) -> None:
        """Return status of debug sessions."""
        session_id = payload.get('session_id')

        with self._debug_sessions_lock:
            if session_id:
                controller = self._debug_sessions.get(session_id)
            else:
                # Snapshot all sessions
                sessions_snapshot = dict(self._debug_sessions)

        if session_id:
            if controller is None:
                self._queue_service.put(
                    self._config.client_control_queue_id,
                    {
                        'type': 'meta_debug_error',
                        'error': f'Debug session not found: {session_id}',
                        'session_id': session_id,
                        'timestamp': timestamp(),
                    },
                )
                return

            self._queue_service.put(
                self._config.client_control_queue_id,
                {
                    'type': 'meta_debug_status',
                    'session_id': session_id,
                    'query': controller.query,
                    'completed_state': (
                        controller.completed_state.value
                        if controller.completed_state
                        else None
                    ),
                    'next_command': controller.next_expected_command,
                    'pipeline_done': controller.pipeline_done,
                    'timestamp': timestamp(),
                },
            )
        else:
            sessions_info = []
            for sid, ctrl in sessions_snapshot.items():
                sessions_info.append({
                    'session_id': sid,
                    'query': ctrl.query,
                    'completed_state': (
                        ctrl.completed_state.value
                        if ctrl.completed_state
                        else None
                    ),
                    'next_command': ctrl.next_expected_command,
                })

            self._queue_service.put(
                self._config.client_control_queue_id,
                {
                    'type': 'meta_debug_status',
                    'sessions': sessions_info,
                    'timestamp': timestamp(),
                },
            )

    def shutdown_debug_sessions(self) -> None:
        """Abort all active debug sessions for graceful shutdown."""
        with self._debug_sessions_lock:
            controllers = list(self._debug_sessions.values())
        for controller in controllers:
            controller.abort()


def _serialize_pipeline_result(result: Any) -> dict:
    """Convert a PipelineResult to a JSON-serializable dict."""
    data: dict = {
        'success': result.failed_stage is None,
        'failed_stage': result.failed_stage,
        'error': result.error,
        'trace_count': len(result.traces),
        'trace_ids': [t.trace_id for t in result.traces],
    }

    if result.graph is not None:
        try:
            data['graph'] = result.graph.to_dict()
        except Exception:
            data['graph'] = str(result.graph)

    if result.synthesis_report is not None:
        try:
            data['synthesis_report'] = result.synthesis_report.to_dict()
        except Exception:
            data['synthesis_report'] = str(result.synthesis_report)

    if result.validation_results is not None:
        try:
            data['validation_results'] = result.validation_results.to_dict()
        except Exception:
            data['validation_results'] = str(result.validation_results)

    if result.python_script is not None:
        data['python_script'] = result.python_script

    if result.evaluation_results:
        data['evaluation_results'] = [
            {'trace_id': r.trace_id, 'passed': r.passed, 'reason': r.reason}
            for r in result.evaluation_results
        ]

    return data
