import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Send, X, ChevronDown, Maximize2, Minimize2, ThumbsUp, ThumbsDown } from 'lucide-react';
import Draggable from 'react-draggable';
import { boltService } from '../lib/services';

const SUGGESTIONS = [
  "What jobs match my skills?",
  "Review my career path",
  "Interview tips for me",
  "Improve my profile",
];

// CSS Avatar with moving eyes
function BoltAvatar({ size = 64, trackMouse = false }: { size?: number; trackMouse?: boolean }) {
  const eyeLeftRef = useRef<HTMLDivElement>(null);
  const eyeRightRef = useRef<HTMLDivElement>(null);
  const avatarRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!trackMouse) return;
    const handleMouseMove = (e: MouseEvent) => {
      const eyes = [eyeLeftRef.current, eyeRightRef.current];
      eyes.forEach((eye) => {
        if (!eye) return;
        const rect = eye.getBoundingClientRect();
        const eyeCenterX = rect.left + rect.width / 2;
        const eyeCenterY = rect.top + rect.height / 2;
        const angle = Math.atan2(e.clientY - eyeCenterY, e.clientX - eyeCenterX);
        const dist = 3;
        const x = Math.cos(angle) * dist;
        const y = Math.sin(angle) * dist;
        eye.style.transform = `translate(${x}px, ${y}px)`;
      });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [trackMouse]);

  const scale = size / 64;

  return (
    <div
      ref={avatarRef}
      style={{
        width: size,
        height: size,
        position: 'relative',
        flexShrink: 0,
      }}
    >
      {/* Body - green ghost shape */}
      <svg
        width={size}
        height={size}
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ position: 'absolute', top: 0, left: 0 }}
      >
        {/* Glow effect */}
        <circle cx="32" cy="32" r="30" fill="rgba(57, 255, 20, 0.1)" />
        {/* Main body */}
        <path
          d="M32 8 C18 8 10 18 10 30 L10 52 L16 46 L22 52 L28 46 L32 50 L36 46 L42 52 L48 46 L54 52 L54 30 C54 18 46 8 32 8Z"
          fill="#39FF14"
          opacity="0.95"
        />
        {/* Shadow/depth */}
        <path
          d="M32 8 C18 8 10 18 10 30 L10 52 L16 46 L22 52 L28 46 L32 50 L36 46 L42 52 L48 46 L54 52 L54 30 C54 18 46 8 32 8Z"
          fill="url(#bodyGrad)"
          opacity="0.3"
        />
        <defs>
          <linearGradient id="bodyGrad" x1="10" y1="8" x2="54" y2="52" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="white" />
            <stop offset="100%" stopColor="#1a7a00" />
          </linearGradient>
        </defs>
        {/* Eye sockets */}
        <ellipse cx="24" cy="30" rx="7" ry="8" fill="#1a1a2e" />
        <ellipse cx="40" cy="30" rx="7" ry="8" fill="#1a1a2e" />
      </svg>

      {/* Moving pupils - left eye */}
      <div
        style={{
          position: 'absolute',
          top: `${22 * scale}px`,
          left: `${17 * scale}px`,
          width: `${14 * scale}px`,
          height: `${16 * scale}px`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'transform 0.05s ease',
        }}
      >
        <div
          ref={eyeLeftRef}
          style={{
            width: `${6 * scale}px`,
            height: `${6 * scale}px`,
            borderRadius: '50%',
            background: 'white',
            transition: 'transform 0.05s ease',
            boxShadow: '0 0 4px rgba(255,255,255,0.8)',
          }}
        />
      </div>

      {/* Moving pupils - right eye */}
      <div
        style={{
          position: 'absolute',
          top: `${22 * scale}px`,
          left: `${33 * scale}px`,
          width: `${14 * scale}px`,
          height: `${16 * scale}px`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'transform 0.05s ease',
        }}
      >
        <div
          ref={eyeRightRef}
          style={{
            width: `${6 * scale}px`,
            height: `${6 * scale}px`,
            borderRadius: '50%',
            background: 'white',
            transition: 'transform 0.05s ease',
            boxShadow: '0 0 4px rgba(255,255,255,0.8)',
          }}
        />
      </div>
    </div>
  );
}

export function BoltAI() {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hi! I'm Bolt AI ✨ Your AI career assistant. How can I help you today?",
      liked: null as boolean | null,
    }
  ]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const draggableRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (text?: string) => {
    const msg = text || input;
    if (!msg.trim()) return;
    setMessages(prev => [...prev, { role: 'user', content: msg, liked: null }]);
    setInput('');
    setLoading(true);
    try {
      const res = await boltService.chat(msg, sessionId);
      setMessages(prev => [...prev, { role: 'assistant', content: res.response, liked: null }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I am unavailable right now.', liked: null }]);
    } finally {
      setLoading(false);
    }
  };

  const handleLike = (idx: number, liked: boolean) => {
    setMessages(prev => prev.map((m, i) => i === idx ? { ...m, liked } : m));
  };

  const chatWidth = isExpanded ? 'w-[600px]' : 'w-96';

  return (
    <Draggable handle=".drag-handle" bounds="body" nodeRef={draggableRef}>
      <div ref={draggableRef} style={{ position: 'fixed', bottom: '2rem', right: '2rem', zIndex: 50 }}>

        {/* Tooltip */}
        <AnimatePresence>
          {showTooltip && !isOpen && (
            <motion.div
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              className="absolute bottom-20 right-0 w-64 glass-card rounded-xl p-3 text-xs text-white/80 border border-white/10"
              style={{ background: 'rgba(15,15,30,0.95)' }}
            >
              💡 Stuck on something? Ask Bolt AI for career guidance, interview tips, and more!
            </motion.div>
          )}
        </AnimatePresence>

        {/* Floating Avatar Button */}
        {!isOpen && (
          <motion.button
            onClick={() => setIsOpen(true)}
            onHoverStart={() => setShowTooltip(true)}
            onHoverEnd={() => setShowTooltip(false)}
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.95 }}
            className="drag-handle relative flex items-center justify-center cursor-pointer"
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'rgba(57, 255, 20, 0.1)',
              border: '2px solid rgba(57, 255, 20, 0.3)',
              boxShadow: '0 0 20px rgba(57, 255, 20, 0.2)',
            }}
          >
            <motion.div
              animate={{ boxShadow: ['0 0 15px rgba(57,255,20,0.3)', '0 0 25px rgba(57,255,20,0.5)', '0 0 15px rgba(57,255,20,0.3)'] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="absolute inset-0 rounded-full"
            />
            <BoltAvatar size={52} trackMouse={true} />
          </motion.button>
        )}

        {/* Chat Panel */}
        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.95 }}
              className={`${chatWidth} rounded-2xl flex flex-col overflow-hidden`}
              style={{
                height: isMinimized ? 'auto' : '580px',
                background: 'rgba(10, 10, 25, 0.97)',
                border: '1px solid rgba(57, 255, 20, 0.2)',
                boxShadow: '0 0 30px rgba(57, 255, 20, 0.1), 0 20px 60px rgba(0,0,0,0.5)',
                backdropFilter: 'blur(20px)',
              }}
            >
              {/* Header */}
              <div
                className="drag-handle p-3 flex items-center justify-between cursor-grab active:cursor-grabbing"
                style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}
              >
                <div className="flex items-center gap-3">
                  <BoltAvatar size={36} trackMouse={true} />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-white">Bolt AI</span>
                      <span
                        className="text-xs px-2 py-0.5 rounded-full"
                        style={{ background: 'rgba(57,255,20,0.15)', color: '#39FF14', border: '1px solid rgba(57,255,20,0.3)' }}
                      >
                        Beta
                      </span>
                    </div>
                    <p className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>Powered by AI</p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
                    title={isExpanded ? 'Collapse' : 'Expand'}
                  >
                    {isExpanded ? <Minimize2 className="w-4 h-4 text-white/60" /> : <Maximize2 className="w-4 h-4 text-white/60" />}
                  </button>
                  <button
                    onClick={() => setIsMinimized(!isMinimized)}
                    className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
                    title="Minimize"
                  >
                    <ChevronDown
                      className="w-4 h-4 text-white/60 transition-transform"
                      style={{ transform: isMinimized ? 'rotate(180deg)' : 'rotate(0deg)' }}
                    />
                  </button>
                  <button
                    onClick={() => setIsOpen(false)}
                    className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
                    title="Close"
                  >
                    <X className="w-4 h-4 text-white/60" />
                  </button>
                </div>
              </div>

              {!isMinimized && (
                <>
                  {/* Messages */}
                  <div
                    className="flex-1 overflow-y-auto p-4 space-y-4"
                    style={{ scrollbarWidth: 'none' }}
                  >
                    {messages.map((msg, idx) => (
                      <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} gap-2`}>
                        {msg.role === 'assistant' && (
                          <BoltAvatar size={28} trackMouse={false} />
                        )}
                        <div className="flex flex-col gap-1 max-w-[80%]">
                          {msg.role === 'assistant' && (
                            <span className="text-xs text-white/40 ml-1">Bolt</span>
                          )}
                          <div
                            className="p-3 rounded-2xl text-sm leading-relaxed"
                            style={{
                              background: msg.role === 'user'
                                ? 'linear-gradient(135deg, rgba(59,130,246,0.8), rgba(139,92,246,0.8))'
                                : 'rgba(255,255,255,0.06)',
                              border: msg.role === 'assistant' ? '1px solid rgba(255,255,255,0.08)' : 'none',
                              color: 'rgba(255,255,255,0.9)',
                            }}
                            dangerouslySetInnerHTML={{
                              __html: msg.content
                                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                                .replace(/\n/g, '<br/>')
                            }}
                          />
                          {/* Thumbs up/down for assistant messages */}
                          {msg.role === 'assistant' && idx > 0 && (
                            <div className="flex gap-2 ml-1">
                              <button
                                onClick={() => handleLike(idx, true)}
                                className="p-1 rounded hover:bg-white/10 transition-colors"
                              >
                                <ThumbsUp
                                  className="w-3 h-3"
                                  style={{ color: msg.liked === true ? '#39FF14' : 'rgba(255,255,255,0.3)' }}
                                />
                              </button>
                              <button
                                onClick={() => handleLike(idx, false)}
                                className="p-1 rounded hover:bg-white/10 transition-colors"
                              >
                                <ThumbsDown
                                  className="w-3 h-3"
                                  style={{ color: msg.liked === false ? '#ef4444' : 'rgba(255,255,255,0.3)' }}
                                />
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}

                    {/* Loading indicator */}
                    {loading && (
                      <div className="flex justify-start gap-2">
                        <BoltAvatar size={28} trackMouse={false} />
                        <div
                          className="p-3 rounded-2xl"
                          style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)' }}
                        >
                          <div className="flex gap-1">
                            {[0, 1, 2].map(i => (
                              <motion.div
                                key={i}
                                className="w-2 h-2 rounded-full"
                                style={{ background: '#39FF14' }}
                                animate={{ opacity: [0.3, 1, 0.3] }}
                                transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
                              />
                            ))}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Suggestions - show only at start */}
                    {messages.length === 1 && !loading && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {SUGGESTIONS.map((s, i) => (
                          <button
                            key={i}
                            onClick={() => handleSend(s)}
                            className="text-xs px-3 py-1.5 rounded-full border transition-colors hover:bg-white/10"
                            style={{
                              border: '1px solid rgba(57,255,20,0.3)',
                              color: 'rgba(255,255,255,0.7)',
                              background: 'rgba(57,255,20,0.05)',
                            }}
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    )}

                    <div ref={messagesEndRef} />
                  </div>

                  {/* Input */}
                  <div
                    className="p-3"
                    style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}
                  >
                    <div className="flex gap-2 items-center">
                      <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                        placeholder="Ask me anything..."
                        className="flex-1 text-sm px-4 py-2 rounded-xl focus:outline-none"
                        style={{
                          background: 'rgba(255,255,255,0.05)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          color: 'rgba(255,255,255,0.9)',
                        }}
                      />
                      <motion.button
                        onClick={() => handleSend()}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        className="p-2 rounded-xl flex items-center justify-center"
                        style={{
                          background: 'linear-gradient(135deg, rgba(57,255,20,0.8), rgba(30,180,10,0.8))',
                        }}
                      >
                        <Send className="w-4 h-4 text-black" />
                      </motion.button>
                    </div>
                  </div>
                </>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </Draggable>
  );
}
