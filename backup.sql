--
-- PostgreSQL database dump
--

-- Dumped from database version 15.13 (Debian 15.13-1.pgdg120+1)
-- Dumped by pg_dump version 15.13 (Debian 15.13-1.pgdg120+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: api_keys; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.api_keys (
    id integer NOT NULL,
    user_id integer NOT NULL,
    exchange_id integer NOT NULL,
    api_key text NOT NULL,
    secret_key text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    is_testnet boolean DEFAULT false
);


ALTER TABLE public.api_keys OWNER TO admin;

--
-- Name: api_keys_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.api_keys_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.api_keys_id_seq OWNER TO admin;

--
-- Name: api_keys_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.api_keys_id_seq OWNED BY public.api_keys.id;


--
-- Name: chat_subscriptions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.chat_subscriptions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    chat_id character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.chat_subscriptions OWNER TO admin;

--
-- Name: chat_subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.chat_subscriptions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.chat_subscriptions_id_seq OWNER TO admin;

--
-- Name: chat_subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.chat_subscriptions_id_seq OWNED BY public.chat_subscriptions.id;


--
-- Name: exchanges; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.exchanges (
    id integer NOT NULL,
    name character varying NOT NULL
);


ALTER TABLE public.exchanges OWNER TO admin;

--
-- Name: exchanges_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.exchanges_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.exchanges_id_seq OWNER TO admin;

--
-- Name: exchanges_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.exchanges_id_seq OWNED BY public.exchanges.id;


--
-- Name: orders; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.orders (
    id integer NOT NULL,
    user_id integer NOT NULL,
    symbol character varying NOT NULL,
    side character varying NOT NULL,
    quantity numeric NOT NULL,
    status character varying NOT NULL,
    entry_price numeric,
    max_entry numeric,
    take_profit numeric,
    stop_loss numeric,
    entry_interval character varying,
    stop_interval character varying,
    executed_price numeric,
    executed_at timestamp with time zone,
    closed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.orders OWNER TO admin;

--
-- Name: orders_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.orders_id_seq OWNER TO admin;

--
-- Name: orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.orders_id_seq OWNED BY public.orders.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying NOT NULL,
    password_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    email character varying NOT NULL,
    telegram_link_code character varying
);


ALTER TABLE public.users OWNER TO admin;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_id_seq OWNER TO admin;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: api_keys id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.api_keys ALTER COLUMN id SET DEFAULT nextval('public.api_keys_id_seq'::regclass);


--
-- Name: chat_subscriptions id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_subscriptions ALTER COLUMN id SET DEFAULT nextval('public.chat_subscriptions_id_seq'::regclass);


--
-- Name: exchanges id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.exchanges ALTER COLUMN id SET DEFAULT nextval('public.exchanges_id_seq'::regclass);


--
-- Name: orders id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.orders ALTER COLUMN id SET DEFAULT nextval('public.orders_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: api_keys; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.api_keys (id, user_id, exchange_id, api_key, secret_key, created_at, is_testnet) FROM stdin;
2	1	1	5gslQFwhB1A2eo5eETDQkHZzsE4fECHvvh2npVLpCkDEuVWPgSOIJNv3GARLdFwK	iyPgm84XXph1VIs3hj3ICpTS8nzrJnMI703y1C7fpByasLKY8pkCugiiC6kK8GgS	2025-05-19 14:12:28.16292+00	f
3	1	1	5gslQFwhB1A2eo5eETDQkHZzsE4fECHvvh2npVLpCkDEuVWPgSOIJNv3GARLdFwK	iyPgm84XXph1VIs3hj3ICpTS8nzrJnMI703y1C7fpByasLKY8pkCugiiC6kK8GgS	2025-05-22 13:50:55.660282+00	t
4	3	1	zInVs5ftJSD07lS5JyCCnaF0SyWYdQKZ5NUHt5bwmdYewMOjcN5bPZnM4aYj1xqC	fDUng45e5pTdVETkNjKO8zqiB7PA3IHXFnTD1LUmpl2LArGen1vakV2u0baXutEJ	2025-05-22 14:14:40.619906+00	f
5	4	1	USwkybBc5hvgExYeJ91l09zwU5jis9H1xEDVpN2Mu60G4FN1hfxzoTLUufojkt5y	gkVAn21lGwtWA136dolXAans2xpFmJrDS4oV9ESj6HIRO4J39a1hPei917K7qBPI	2025-05-27 10:13:23.400602+00	f
\.


--
-- Data for Name: chat_subscriptions; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.chat_subscriptions (id, user_id, chat_id, created_at) FROM stdin;
2	3	20323397	2025-05-22 18:27:04.903456+00
\.


--
-- Data for Name: exchanges; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.exchanges (id, name) FROM stdin;
1	binance
\.


--
-- Data for Name: orders; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.orders (id, user_id, symbol, side, quantity, status, entry_price, max_entry, take_profit, stop_loss, entry_interval, stop_interval, executed_price, executed_at, closed_at, created_at) FROM stdin;
7	1	BNBUSDC	LONG	1.0	CANCELLED	1000.0	1000.0	1100.0	950.0	M5	M5	\N	\N	2025-05-19 15:26:21.043198+00	2025-05-19 15:26:14.962408+00
8	1	BNBUSDC	LONG	1.0	CANCELLED	645.0	649.0	660.0	640.0	M5	M5	\N	\N	2025-05-19 18:19:30.904207+00	2025-05-19 18:01:29.058099+00
9	1	BNBUSDC	LONG	1.0	CANCELLED	645.72	645.72	660.0	630.0	M5	M5	\N	\N	\N	2025-05-19 18:21:06.800167+00
30	3	BNBUSDC	LONG	0.030000000000000002	CLOSED_TP	673.0	678.0	680.0	650.0	M5	M5	680.0	2025-05-24 15:55:39.833207+00	\N	2025-05-24 15:54:13.881495+00
10	1	BNBUSDC	LONG	1.0	CLOSED_TP	647.0	655.0	670.0	602.0	M5	M5	670.0	2025-05-20 11:59:37.805254+00	\N	2025-05-20 08:42:36.359589+00
13	1	BNBUSDC	LONG	0.00001	CANCELLED	105100.0	105100.0	105800.0	100000.0	M5	M5	\N	\N	2025-05-20 12:03:18.518598+00	2025-05-20 12:03:08.88539+00
31	3	BNBUSDC	LONG	0.03	CANCELLED	674.0	679.0	690.0	650.0	M5	M5	\N	\N	2025-05-24 16:02:20.272452+00	2025-05-24 16:01:45.168384+00
11	1	BNBUSDC	LONG	1.0	CANCELLED	646.0	646.0	680.0	642.0	M5	M5	\N	\N	\N	2025-05-20 11:54:38.317436+00
14	1	BTCUSDC	LONG	0.0001	CLOSED_TP	105100.0	105400.0	106000.01	103000.0	M5	M5	106000.01	2025-05-20 17:13:36.905007+00	\N	2025-05-20 12:03:52.486713+00
12	1	BNBUSDC	LONG	0.00001	CANCELLED	105200.0	105200.0	105400.01	100000.0	M5	M5	\N	\N	2025-05-21 08:59:51.362704+00	2025-05-20 12:02:23.754997+00
15	3	TRXUSDC	LONG	5000.0	CANCELLED	0.28	0.28	0.31	0.24	M5	Daily	\N	\N	2025-05-22 15:16:41.318069+00	2025-05-22 15:11:57.398118+00
16	3	TRXUSDC	LONG	5000.0	CANCELLED	0.2784	0.2784	0.31	0.247	M5	Daily	\N	\N	\N	2025-05-22 15:18:31.510934+00
17	3	TRXUSDC	LONG	5000.0	CANCELLED	0.278	0.278	0.31	0.24	M5	Daily	\N	\N	2025-05-22 15:34:19.706998+00	2025-05-22 15:34:12.48135+00
32	3	BNBUSDC	LONG	0.030000000000000002	CLOSED_TP	673.0	678.0	680.0	660.0	M5	M5	680.0	2025-05-24 16:05:39.186672+00	\N	2025-05-24 16:02:12.458298+00
19	3	ETHUSDC	LONG	0.3	CANCELLED	2710.0	2710.0	3000.0	2550.0	Daily	Daily	\N	\N	2025-05-22 19:51:20.078971+00	2025-05-22 17:53:37.008343+00
20	3	ETHUSDC	LONG	0.3	CANCELLED	2700.0	2700.0	3440.0	2400.0	Daily	Daily	\N	\N	2025-05-22 19:55:16.651112+00	2025-05-22 19:52:02.011223+00
22	3	SOLUSDC	LONG	3.0	CANCELLED	189.0	189.0	202.0	167.5	Daily	Daily	\N	\N	2025-05-23 09:16:22.172973+00	2025-05-23 09:13:45.036765+00
57	3	SOLUSDC	LONG	8.0	CANCELLED	166.5	171.5	184.0	158.0	Daily	Daily	\N	\N	2025-07-17 07:51:28.619008+00	2025-07-16 17:14:27.444401+00
23	3	SOLUSDC	LONG	3.0	CANCELLED	187.0	190.0	202.0	167.5	Daily	Daily	\N	\N	2025-05-23 17:56:06.818288+00	2025-05-23 09:19:42.742264+00
21	3	ETHUSDC	LONG	0.3	CLOSED_MANUAL	2700.0	2800.0	3400.0	2399.99	Daily	Daily	2698.5	2025-05-23 02:14:36.660972+00	2025-05-24 12:43:49.464223+00	2025-05-22 19:55:42.547735+00
24	3	BNBUSDC	LONG	0.0001	CANCELLED	673.0	673.0	690.0	140.0	M5	M5	\N	\N	\N	2025-05-24 13:34:53.835597+00
25	3	BNBUSDC	LONG	0.00001	CANCELLED	673.0	673.0	690.0	640.0	M5	M5	\N	\N	\N	2025-05-24 13:41:37.321127+00
26	3	BNBUSDC	LONG	0.00001	CANCELLED	673.0	680.0	700.0	600.0	M5	M5	\N	\N	2025-05-24 15:31:29.958619+00	2025-05-24 13:47:08.580196+00
27	3	BNBUSDC	LONG	0.00001	CANCELLED	671.0	676.0	690.0	640.0	M5	M5	\N	\N	2025-05-24 15:31:33.523247+00	2025-05-24 13:57:27.761312+00
29	3	BNBUSDC	LONG	0.05	CLOSED_MANUAL	672.0	677.0	690.0	640.0	M5	M5	673.12	2025-05-24 15:40:37.588766+00	2025-05-24 15:53:38.195375+00	2025-05-24 15:38:07.868276+00
28	3	BNBUSDC	LONG	0.001	CANCELLED	672.0	677.0	690.0	640.0	M5	M5	\N	\N	2025-05-24 15:53:52.505559+00	2025-05-24 15:31:57.869948+00
51	3	BTCUSDC	LONG	0.01	CANCELLED	107440.0	108200.0	112999.0	104620.0	Daily	Daily	\N	\N	2025-06-30 08:10:24.262802+00	2025-06-25 13:32:29.531066+00
44	3	BNBUSDC	LONG	0.05	CANCELLED	700.0	750.0	800.0	400.0	M5	M5	\N	\N	2025-05-25 08:10:23.87131+00	2025-05-25 08:10:16.730659+00
33	3	BNBUSDC	LONG	0.03	CLOSED_MANUAL	673.0	678.0	690.0	640.0	M5	M5	673.89	2025-05-24 16:10:37.144875+00	2025-05-24 16:22:16.704361+00	2025-05-24 16:08:14.287751+00
34	3	BNBUSDC	LONG	0.03	CLOSED_MANUAL	673.0	678.0	690.0	640.0	M5	M5	673.06	2025-05-24 16:15:36.699156+00	2025-05-24 16:22:16.939597+00	2025-05-24 16:13:29.764171+00
35	3	BNBUSDC	LONG	0.03	CLOSED_MANUAL	673.0	678.0	690.0	650.0	M5	M5	673.94	2025-05-24 16:21:01.424132+00	2025-05-24 16:22:17.178111+00	2025-05-24 16:18:31.699049+00
36	3	BNBUSDC	LONG	0.03	CLOSED_MANUAL	673.0	678.0	690.0	640.0	M5	M5	673.59	2025-05-24 16:31:01.41382+00	2025-05-24 17:08:08.502327+00	2025-05-24 16:26:10.440003+00
37	3	BNBUSDC	LONG	0.03	CLOSED_MANUAL	673.0	678.0	700.0	650.0	M5	M5	675.52	2025-05-24 16:51:01.424996+00	2025-05-24 17:08:08.736444+00	2025-05-24 16:45:28.085548+00
38	3	BNBUSDC	LONG	0.03	CLOSED_MANUAL	675.0	680.0	700.0	640.0	M5	M5	675.41	2025-05-24 17:06:01.406836+00	2025-05-24 17:08:08.975233+00	2025-05-24 17:00:21.558363+00
41	3	ETHUSDC	LONG	0.03	CANCELLED	2710.0	2715.0	3400.0	2400.0	Daily	Daily	\N	\N	2025-05-25 11:44:36.853229+00	2025-05-24 17:52:29.364325+00
43	3	BTCUSDC	LONG	0.007	CANCELLED	110534.99	110540.0	119012.0	106900.0	Daily	Daily	\N	\N	2025-05-26 08:40:06.846113+00	2025-05-24 18:14:09.232657+00
48	3	BTCUSDC	LONG	0.015	CANCELLED	110535.0	112000.0	119015.0	106900.0	Daily	Daily	\N	\N	2025-05-28 13:11:48.997317+00	2025-05-27 13:20:59.036872+00
18	3	TRXUSDC	LONG	5000.0	CLOSED_EXTERNALLY	0.278	0.3	0.31	0.22999999999999998	M5	Daily	0.2783	2025-05-22 16:05:36.671988+00	2025-07-11 14:30:57.511772+00	2025-05-22 15:39:13.672595+00
40	3	BNBUSDC	LONG	0.03	CLOSED_MANUAL	674.0	679.0	700.01	641.01	M5	M5	674.72	2025-05-24 17:21:29.082082+00	2025-05-24 17:41:21.575821+00	2025-05-24 17:17:46.084561+00
39	3	BNBUSDC	LONG	0.03	CLOSED_MANUAL	674.0	679.0	700.0	641.01	M5	M5	675.15	2025-05-24 17:16:01.413189+00	2025-05-24 17:41:36.359241+00	2025-05-24 17:11:45.576659+00
53	3	XRPUSDC	LONG	300.0	CLOSED_TP	2.3	2.35	2.81	2.16	M5	Daily	2.3376	2025-07-09 08:20:05.8784+00	2025-07-12 14:51:52.599353+00	2025-07-09 08:12:55.969673+00
59	3	AVAXUSDC	LONG	50.0	IN_EXECUTION	22.0	23.0	38.0	21.0	M5	Daily	\N	\N	\N	2025-07-17 16:32:07.573375+00
50	3	UNIUSDC	LONG	120.0	CANCELLED	8.15	9.15	8.79	7.6	Daily	Daily	\N	\N	2025-07-10 14:22:36.435073+00	2025-06-17 10:27:59.500056+00
46	3	UNIUSDC	LONG	120.0	CLOSED_EXTERNALLY	6.5	7.0	8.36	6.15	M5	Daily	6.549	2025-05-26 08:45:30.511079+00	2025-06-11 08:15:05.992155+00	2025-05-26 08:41:26.54516+00
49	3	XRPUSDC	LONG	900.0	CLOSED_SL	2.26	2.35	3.03	2.18	M5	Daily	\N	2025-05-28 14:44:04.503969+00	2025-06-14 00:00:05.106347+00	2025-05-28 13:13:22.116742+00
45	3	ETHUSDC	LONG	0.2999	CLOSED_SL	2710.0	2800.0	3470.0	2400.0	Daily	M5	2720.4	2025-05-29 01:00:53.581779+00	2025-06-22 14:22:06.291635+00	2025-05-25 11:44:32.263543+00
55	3	AAVEUSDC	LONG	3.5	CLOSED_TP	303.5	312.5	327.0	303.0	Daily	Daily	306.72	2025-07-14 00:03:52.249958+00	2025-07-14 06:33:51.463483+00	2025-07-11 14:33:39.846802+00
54	3	UNIUSDC	LONG	120.0	CANCELLED	8.05	8.5	8.79	7.6	M5	Daily	\N	\N	2025-07-10 15:32:07.799779+00	2025-07-10 14:22:47.973874+00
52	3	BTCUSDC	LONG	0.00999	CLOSED_MANUAL	107440.0	107945.0	112999.0	104620.0	M5	Daily	107605.29	2025-06-30 08:21:03.296839+00	2025-07-11 13:16:46.312252+00	2025-06-30 08:10:13.415402+00
42	3	SOLUSDC	LONG	5.0	CLOSED_MANUAL	144.0	154.0	167.0	140.0	Daily	Daily	152.51	2025-07-02 16:16:04.031073+00	2025-07-11 13:19:47.77805+00	2025-05-24 17:54:57.136182+00
60	3	AVAXUSDC	LONG	50.0	IN_EXECUTION	22.0	23.01	38.0	21.0	M5	Daily	\N	\N	\N	2025-07-17 16:46:10.586219+00
56	3	AAVEUSDC	LONG	5.000000000000001	CLOSED_TP	330.0	350.0	395.0	311.0	M5	Daily	333.56	2025-07-16 07:47:51.841569+00	2025-07-16 17:09:50.809507+00	2025-07-16 07:39:26.668213+00
58	3	AVAXUSDC	LONG	50.0	IN_EXECUTION	22.62	22.9	38.0	21.3	M5	Daily	\N	\N	\N	2025-07-17 07:52:38.506859+00
61	3	AVAXUSDC	LONG	50.0	IN_EXECUTION	22.0	23.0	38.0	21.0	M5	Daily	\N	\N	\N	2025-07-17 16:52:25.50913+00
62	3	AVAXUSDC	LONG	50.0	IN_EXECUTION	22.0	23.0	38.0	21.0	M5	Daily	\N	\N	\N	2025-07-17 16:58:37.136178+00
65	3	SOLUSDC	LONG	5.0	CLOSED_SL	179.0	184.0	220.0	160.0	M5	Daily	179.89	2025-07-18 09:56:54.781953+00	2025-08-03 00:00:57.439661+00	2025-07-18 09:49:14.906708+00
64	3	AAVEUSDC	LONG	5.0	CLOSED_SL	320.0	330.0	395.0	312.0	M5	Daily	327.29	2025-07-18 08:50:54.771245+00	2025-07-23 00:00:56.013874+00	2025-07-18 08:43:46.039913+00
66	3	SOLUSDC	LONG	5.0	CLOSED_SL	184.0	189.0	220.0	161.0	M5	Daily	189.2	2025-07-21 06:46:54.993931+00	2025-08-03 00:01:00.061497+00	2025-07-21 06:29:52.965514+00
67	3	TONUSDC	LONG	300.0	CANCELLED	3.25	3.5	4.1	2.97	Daily	Daily	\N	\N	2025-07-27 07:44:34.023263+00	2025-07-26 15:33:08.946576+00
63	3	AVAXUSDC	LONG	50.0	CLOSED_SL	22.0	23.0	37.99	21.0	M5	Daily	22.57	2025-07-17 17:36:47.143614+00	2025-08-03 00:00:54.847341+00	2025-07-17 17:08:51.717727+00
68	3	TONUSDC	LONG	300.0	CLOSED_SL	3.25	3.5	4.1	2.97	M5	Daily	3.338	2025-07-27 07:50:54.719629+00	2025-09-23 00:00:55.198535+00	2025-07-27 07:44:40.78773+00
69	3	AAVEUSDC	LONG	3.5	CANCELLED	271.0	282.0	303.0	250.0	Daily	Daily	\N	\N	2025-08-08 13:17:38.470101+00	2025-08-07 20:46:12.363882+00
71	3	AAVEUSDC	LONG	3.5	CLOSED_EXTERNALLY	281.0	286.0	303.0	250.0	M5	Daily	282.57	2025-08-08 13:26:56.074588+00	2025-08-09 08:34:55.316111+00	2025-08-08 13:17:32.05213+00
70	3	SOLUSDC	LONG	7.0	CLOSED_EXTERNALLY	172.0	177.0	184.5	166.5	H4	Daily	174.75	2025-08-08 04:00:56.222122+00	2025-08-13 08:17:50.830736+00	2025-08-07 20:47:14.013926+00
72	3	SOLUSDC	LONG	6.0	CLOSED_SL	198.0	203.0	220.0	184.5	M5	Daily	199.74	2025-08-13 18:06:55.022174+00	2025-08-19 00:00:55.60606+00	2025-08-13 17:58:51.890163+00
75	3	ADAUSDC	LONG	600.0	EXECUTED	0.84	0.86	0.95	0.78	M5	Daily	0.8448	2025-09-08 09:00:55.595208+00	\N	2025-09-08 08:52:57.080221+00
74	3	SOLUSDC	LONG	7.0	CLOSED_EXTERNALLY	200.0	211.01	230.0	164.0	M5	Daily	203.23	2025-08-23 10:30:55.550685+00	2025-09-11 07:55:19.932324+00	2025-08-23 10:23:55.25539+00
73	3	SOLUSDC	LONG	7.0	CLOSED_EXTERNALLY	191.0	205.0	233.0	180.0	Daily	Daily	204.39	2025-08-24 00:00:55.11797+00	2025-09-11 07:55:33.730651+00	2025-08-22 18:54:39.296437+00
77	3	BNBUSDC	LONG	1.2	CLOSED_EXTERNALLY	919.0	927.0	957.0	852.0	Daily	Daily	919.89	2025-09-16 00:00:55.02798+00	2025-09-17 07:23:52.486694+00	2025-09-12 19:11:51.355464+00
78	3	SOLUSDC	LONG	5.0	CLOSED_SL	237.0	242.0	272.0	228.0	M5	Daily	237.53	2025-09-17 07:30:54.708775+00	2025-09-23 00:00:58.266432+00	2025-09-17 07:24:46.936104+00
79	3	ATOMUSDC	LONG	120.00000000000001	CLOSED_SL	4.57	4.6	7.95	4.2	M5	Daily	4.586	2025-09-18 07:56:54.629112+00	2025-09-23 00:01:00.27081+00	2025-09-18 07:45:04.835204+00
81	3	SOLUSDC	LONG	5.0	CLOSED_EXTERNALLY	202.0	209.0	220.0	197.0	M5	Daily	208.99	2025-09-29 08:34:54.885352+00	2025-10-03 06:44:07.94885+00	2025-09-29 08:24:54.832364+00
80	3	AVAXUSDC	LONG	35.0	CLOSED_SL	29.0	34.0	32.0	28.8	M5	Daily	29.8	2025-09-29 08:30:54.803918+00	2025-10-08 00:00:55.824918+00	2025-09-29 08:24:28.130832+00
82	3	XRPUSDC	LONG	470.0	CLOSED_SL	3.03	3.08	3.4	2.85	M5	Daily	3.0334	2025-10-03 07:20:54.674439+00	2025-10-10 00:00:55.914223+00	2025-10-03 06:43:44.459532+00
76	3	UNIUSDC	LONG	200.0	CLOSED_SL	9.89	10.0	15.0	7.0	M5	Daily	9.909	2025-09-11 08:06:54.787995+00	2025-10-11 00:00:58.49335+00	2025-09-11 07:57:48.315996+00
83	3	ATOMUSDC	LONG	500.0	CANCELLED	3.05	3.2	3.95	2.7	Daily	Daily	\N	\N	2025-11-21 11:03:43.442512+00	2025-11-20 10:48:22.664998+00
84	3	BTCUSDC	LONG	0.02999	CLOSED_SL	91660.0	91765.0	98800.0	87820.0	M5	Daily	91666.34	2025-11-28 09:15:31.851652+00	2025-12-02 00:01:35.619903+00	2025-11-28 09:12:14.027308+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.users (id, username, password_hash, created_at, email, telegram_link_code) FROM stdin;
1	Admin	scrypt:32768:8:1$Sjp958rHURaYUqxG$dd85f22fb6ff2be286ce66613f4fd718d59798c2137490a8ee720a1cbc37af8823df3de29e08d730e6138f761c991d55f21a8c62dac549cc02a0d05f3d2b5e8c	2025-05-14 12:06:27.592705+00	annunziatoco@gmail.com	b67615e8
3	nunzio	scrypt:32768:8:1$9UCxlVCkaQCL0XXD$9058fe1cb3259d792d6bd66b621cd649ac48e734b14fb345aa7beb5d0c4b7561e4f65c44f79a39850119468549b8a590e7f02819f796cb8422df98763fb14664	2025-05-22 14:04:36.673235+00	annunziatoco@yahoo.com	93a71c0f
4	maruscya	scrypt:32768:8:1$AQxbQivpDYSaxNa1$a8b523d7ed98f007935dddb69c8673a7763e8b9576bcef9cf352a98bd97d5ea9a27eaeb06455639640181a7b457c4e81a54f9ddcb2344469f26791fb94c5502b	2025-05-27 09:57:51.342819+00	bazzanini.andrea@gmail.com	b91ec838
\.


--
-- Name: api_keys_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.api_keys_id_seq', 5, true);


--
-- Name: chat_subscriptions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.chat_subscriptions_id_seq', 2, true);


--
-- Name: exchanges_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.exchanges_id_seq', 1, true);


--
-- Name: orders_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.orders_id_seq', 84, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.users_id_seq', 4, true);


--
-- Name: api_keys api_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);


--
-- Name: chat_subscriptions chat_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_subscriptions
    ADD CONSTRAINT chat_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: exchanges exchanges_name_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.exchanges
    ADD CONSTRAINT exchanges_name_key UNIQUE (name);


--
-- Name: exchanges exchanges_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.exchanges
    ADD CONSTRAINT exchanges_pkey PRIMARY KEY (id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: api_keys api_keys_exchange_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_exchange_id_fkey FOREIGN KEY (exchange_id) REFERENCES public.exchanges(id) ON DELETE CASCADE;


--
-- Name: api_keys api_keys_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: chat_subscriptions chat_subscriptions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.chat_subscriptions
    ADD CONSTRAINT chat_subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: orders orders_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

