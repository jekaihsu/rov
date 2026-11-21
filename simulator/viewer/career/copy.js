// Localized copy for career data files (contracts.json, licences.json, equipment.json).
// Stable keys are entity ids; Traditional Chinese source matches the JSON. UI reads through helpers in
// localize_data.js so game ids stay untranslated. Key scheme: career.copy.<bucket>.<id>.<field>
// (PROTOCOL.md “前端依穩定 key 翻譯”).
import { localize } from '../i18n/index.js';

const STRINGS = localize('career.copy', {
  clients: {
    yx: {
      label: "YX 海事服務"
    },
    harbor: {
      label: "港務"
    },
    shipping: {
      label: "船東與船管"
    },
    marine_works: {
      label: "海事工程"
    },
    aquaculture: {
      label: "養殖業者"
    }
  },
  jobs: {
    training: "公司內訓",
    checkout: "下水檢查潛",
    familiarization: "開放水域熟悉",
    gvi: "一般目視檢查（GVI）",
    marine_growth: "海生物量測（Level II）",
    fouling: "船殼附著評級",
    search: "搜尋與確認",
    cp: "陰極防蝕量測（CP）",
    ut: "超音波測厚（UT）",
    net: "網衣巡檢",
    recovery: "回收作業",
    mooring: "繫泊檢查"
  },
  chapters: {
    prologue: {
      title: "序章 · 見習之前",
      summary: "青嶼港訓練水池與港外避風水域：走完程序，拿下見習駕駛員執照。"
    },
    ch1: {
      title: "第一章 · 港口與船舶",
      summary: "漁港碼頭、貨輪船殼與港內搜尋。章末交班複查是二級駕駛員考核。"
    },
    ch2: {
      title: "第二章 · 養殖場",
      summary: "外海箱網：網衣、死魚與繫泊。需要二級駕駛員執照。"
    }
  },
  contracts: {
    p0_induction: {
      title: "新人內訓：水池操作課",
      clientName: "YX 海事服務 · 訓練",
      summary: "馬力陪飛。到北牆觀察鬆桿時的深度變化，再拍三面標板。",
      brief: "青嶼港訓練池，淡水、無流。周楷看纜，馬力帶飛。依次帶回北、東、南三面標板的照片，由林岑點收。",
      radio: {
        speaker: "林岑",
        start: "向潮－指揮呼叫 R-1。今天池裡認識搭檔。先檢查。",
        done: "收工。程序過了。"
      }
    },
    p1_pool_checkout: {
      title: "水池檢查潛",
      clientName: "YX 海事服務 · 訓練",
      summary: "水池檢查潛：解鎖、懸停、三面池壁各拍一張、回投放點。約 15–20 分。",
      brief: "工單 YX-TR-001。載具 YX Model R。完成預潛檢查表後入水；解鎖推進器，池中央懸停 20 秒，北、東、南三面池壁各拍一張帶疊字照片，最後回投放點等回收。水面外禁止解鎖。",
      radio: {
        speaker: "林岑",
        start: "入水。人離甲板再解鎖。",
        done: "照片夠了。準備回收。",
        partial: "人機回來就好。重跑本趟。"
      },
      deliverables: {
        unlock: "解鎖推進器",
        hover: "池中央懸停 20 秒（偏移 < 0.6 m）",
        photo_north: "北池壁照片",
        photo_east: "東池壁照片",
        photo_south: "南池壁照片",
        depth_hold: "定深功能確認",
        recover: "回投放點，準備回收"
      }
    },
    p2_open_water: {
      title: "開放水域熟悉（見習考核）",
      clientName: "YX 海事服務 · 訓練",
      summary: "見習考核：四個浮標檢查點、定深、鬆桿看漂移。全程真實模式。約 15–20 分。",
      brief: "工單 YX-TR-002。青嶼港外避風水域。依序通過四個檢查點，定深保持，途中鬆桿觀察漂移再穩住，回投放點。微流；推力不等於速度。考核強制真實設定。通過後頒發見習駕駛員執照。",
      radio: {
        speaker: "林岑",
        start: "R-1，四個浮標檢查點。依序。",
        done: "熟悉夠了。回船。",
        partial: "回來對。重跑熟悉趟。"
      },
      deliverables: {
        unlock: "解鎖推進器",
        cp1: "檢查點 1",
        depth_hold: "開啟定深",
        cp2: "檢查點 2",
        drift: "懸停 15 秒，觀察漂移",
        cp3: "檢查點 3",
        cp4: "檢查點 4",
        recover: "回投放點上浮"
      }
    },
    c1_pier_level1: {
      title: "碼頭外的第一張工單",
      clientName: "北堤漁港管理處",
      summary: "Level I 巡視：棧橋六根樁各拍一張樁身照，纜線不要繞樁。",
      brief: "管理處要在颱風季前做一次 Level I 巡視，只要覆蓋、不要量測。棧橋下 A、B 兩列共六根樁，每根在水深約 6 m 拍一張樁身照，看得到樁就算。橫流偏東，繞樁前先想好怎麼退，回收時纜線不能纏在樁上。碼頭壁面有空就順手拍一張，管理處會很感激（但不會多付錢）。",
      radio: {
        speaker: "林督導",
        start: "第一張外面的單子。阿禾在甲板看線，你專心看樁。",
        done: "管理處說照片很清楚。他們以前收過一整卷只拍到泥巴的。",
        partial: "先交這些。剩下的樁我跟管理處說改天補。"
      },
      deliverables: {
        pile_a1: "A 列 1 號樁",
        pile_a2: "A 列 2 號樁",
        pile_a3: "A 列 3 號樁",
        pile_b1: "B 列 1 號樁",
        pile_b2: "B 列 2 號樁",
        pile_b3: "B 列 3 號樁",
        quay: "碼頭壁面概況（加分）",
        recover: "回投放點回收"
      }
    },
    c1_pier_level2: {
      title: "碼頭 Level II 抽樣：海生物量測",
      clientName: "北堤漁港管理處",
      summary: "指定三根樁、各兩個高程，用雷射比例尺量海生物厚度。",
      brief: "上次的照片管理處看完，想知道附著到底多厚。這次是 Level II 抽樣：A1、A3、B2 三根樁，在水深 4 m 和 12 m 各量一次。貼近到 1 m 左右、正對樁面、停穩，讓雷射點落在附著層上，讀數穩了才算。量完照常回投放點。",
      radio: {
        speaker: "林督導",
        start: "雷射點要落在藤壺上，不是落在魚上。",
        done: "數字很漂亮。管理處說要拿去跟去年比，你可以當作被誇了。",
        partial: "缺的那幾點我記下來，下次潮況好再補。"
      },
      deliverables: {
        a1_upper: "A1 樁 · 水深 4 m",
        a1_lower: "A1 樁 · 水深 12 m",
        a3_upper: "A3 樁 · 水深 4 m",
        a3_lower: "A3 樁 · 水深 12 m",
        b2_upper: "B2 樁 · 水深 4 m",
        b2_lower: "B2 樁 · 水深 12 m",
        b2_photo: "B2 樁附著層近照（加分）",
        recover: "回投放點回收"
      }
    },
    c1_hull_fouling: {
      title: "貨輪船殼附著評級",
      clientName: "海鷗航運船管部",
      summary: "80 m 貨輪：兩側舭龍骨、螺槳、舵各拍一張評級照。靠近螺槳前先確認 LOTO。",
      brief: "船管部要決定這次靠港要不要順便清船底。拍兩側舭龍骨、螺槳葉片、舵各一張，讓他們照照片給附著評級。螺槳區先跟船上確認主機停機、軸系上鎖（LOTO），沒確認之前離螺槳三公尺以內就算安全違規。船底下面沒有水面可以參考，留意自己的深度和纜線。",
      radio: {
        speaker: "阿禾",
        start: "輪機長說主機停了，但你還是要聽到他親口說上鎖。",
        done: "船管說評級夠清楚，他們決定下週再清，算你幫公司省錢。",
        partial: "有拍到的先給船管，螺槳那邊下次再來。"
      },
      deliverables: {
        keel_starboard: "右舷舭龍骨",
        keel_port: "左舷舭龍骨",
        loto: "主機停機、軸系上鎖（LOTO）",
        propeller: "螺槳葉片",
        rudder: "舵",
        recover: "回投放點回收"
      }
    },
    c1_dropped_object: {
      title: "港內掉落物",
      clientName: "北堤疏濬工程隊",
      summary: "能見度不到一公尺：先用聲納找到掉落的測量儀，再貼近用相機確認。",
      brief: "工程隊的測量儀從工作船上掉下去了，大概在投放點東北方二十公尺內。水很濁，相機看不到一公尺。坐底用成像聲納掃，讀方位、轉向，慢慢接近回波，貼近到能看清楚再拍照確認。不要用推進器把泥打起來，那樣你也什麼都看不到。",
      radio: {
        speaker: "工程隊 老蔡",
        start: "那台儀器比我的車還貴，拜託了。",
        done: "找到了！潛水員下午去掛繩。我欠你一個便當。",
        partial: "至少知道大概在哪了，謝啦。"
      },
      deliverables: {
        contact: "以聲納找到回波並接近",
        confirm_photo: "相機確認：測量儀",
        recover: "回投放點回收"
      }
    },
    c1_quay_cp: {
      title: "碼頭鋼板樁防蝕抽測",
      clientName: "北堤漁港管理處",
      summary: "支線：碼頭壁三個點用 CP 探針頂住讀電位，找出保護不足的地方。",
      brief: "管理處對我們有點信心了，追加一張小單：碼頭壁三個抽測點量陰極防蝕電位。探針要輕輕頂住壁面、停穩幾秒才有讀數；撞上去讀數不算，還會被扣分。讀數比 −800 mV 正的地方就是保護不足，報告裡要標出來。",
      radio: {
        speaker: "林督導",
        start: "這次是要你碰它，但要溫柔地碰。",
        done: "第三點保護不足，管理處會安排換陽極。很好的發現。",
        partial: "先交這兩點。"
      },
      deliverables: {
        cp_west: "碼頭壁 南段 · 水深 6 m",
        cp_mid: "碼頭壁 中段 · 水深 10 m",
        cp_east: "碼頭壁 北段 · 水深 6 m",
        recover: "回投放點回收"
      }
    },
    c1_hull_ut: {
      title: "船殼測厚抽點",
      clientName: "海鷗航運船管部",
      summary: "支線：船殼舷側四個點用超音波測厚，船級年檢要用。",
      brief: "船管部的船級年檢需要舷側抽點測厚。左右舷、船中前後各一點，水深約 4 m。探頭要貼住鋼板、停穩，讀數才可信。這次不靠近螺槳，但船底下面一樣沒有水面參考。",
      radio: {
        speaker: "阿禾",
        start: "四個點，量完就收工。今天甲板便當是排骨。",
        done: "都在容許範圍內。驗船師會很開心，船東會更開心。",
        partial: "缺的點驗船師會再要，先交。"
      },
      deliverables: {
        ut_sb_fwd: "右舷 船中前",
        ut_sb_aft: "右舷 船中後",
        ut_ps_fwd: "左舷 船中前",
        ut_ps_aft: "左舷 船中後",
        recover: "回投放點回收"
      }
    },
    c1_signoff_exam: {
      title: "章末：交班前複查（二級考核）",
      clientName: "北堤漁港管理處",
      summary: "二級考核：回到上次的三個異常點，照原本的角度重拍，讓下一班找得到。全程真實模式。",
      brief: "這是二級駕駛員考核，也是一張真的工單：管理處要比對上次記下的三個異常有沒有惡化。"
        + "A2 樁水深 10 m 的裂痕、B3 樁水深 14 m 的混凝土剝落、碼頭壁南段水深 12 m 的缺角，"
        + "各從原本的位置（約 1–2.5 m）正對重拍；碼頭壁中段再做一次 6 秒定點目視。纜線不要繞樁，回收前全部做完。",
      radio: {
        speaker: "林督導",
        start: "考官還是我。照片要讓下一班的人看得懂，這就是考題。",
        done: "通過。二級證會寄到公司，下個月開始你可以接養殖場的案子了。",
        partial: "差一點。照片角度再練練，下週再考。"
      },
      deliverables: {
        a2_crack: "A2 樁 · 水深 10 m 裂痕",
        b3_spall: "B3 樁 · 水深 14 m 剝落",
        quay_chip: "碼頭壁南段 · 水深 12 m 缺角",
        quay_station: "碼頭壁中段 · 定點目視 6 秒",
        recover: "回投放點回收"
      }
    },
    c2_net_inspection: {
      title: "網衣巡檢",
      clientName: "東澳外海箱網場",
      summary: "平潮時沿箱網外側繞一圈，找出兩個網衣破洞並拍照。靠太近推進器會吸網。",
      brief: "場長說最近每天少魚，懷疑網衣破了。趁平潮從網外側繞一圈（東、北、西、南四個方位都要經過），看到破洞就停下來正對拍照。不要貼網太近，推進器會把網衣吸過來；纜線也別跨過繫泊纜。",
      radio: {
        speaker: "場長 阿美",
        start: "魚很怕生，你慢一點，牠們就不會亂跑。",
        done: "兩個洞都找到了，今天下午就補。謝謝你們。",
        partial: "先補找到的這個，剩下的明天平潮再看。"
      },
      deliverables: {
        ring_south: "南側網外（水深 7 m）",
        ring_east: "東側網外",
        ring_north: "北側網外",
        ring_west: "西側網外",
        hole_upper: "破洞 · 水深約 7 m",
        hole_lower: "破洞 · 水深約 13 m",
        recover: "回投放點回收"
      }
    },
    c2_mort_recovery: {
      title: "死魚回收（Model V）",
      clientName: "東澳外海箱網場",
      summary: "從網邊走道把 Model V 放進網內，用夾爪把網底的死魚夾起來。需要機械臂，只能派 Model V。",
      brief: "網底積了幾尾死魚，放著會壞水質。這次從箱網走道直接把機子放進網內，只有 Model V 有機械臂，所以派它。下到網底，一尾一尾夾起來提離網底；夾住以後配平會變，慢慢來，碰網底會驚動整箱魚。",
      radio: {
        speaker: "場長 阿美",
        start: "這工作不好看，但很重要。",
        done: "網底乾淨多了。下次請你吃魚，活的那種。",
        partial: "先收這些，剩下的我們用撈網。"
      },
      deliverables: {
        first_fish: "夾起一尾死魚並提離網底",
        second_fish: "再回收一尾（加分）",
        recover: "回到網內下水點回收"
      }
    },
    c2_mooring_exam: {
      title: "章末：颱風過後的錨繩（箱網簽注考核）",
      clientName: "東澳外海箱網場",
      summary: "沿南側兩條錨繩從浮標看到錨，記錄錨繩狀況。全程真實模式。",
      brief: "颱風剛過，場長要確認繫泊還撐得住。從東南、西南兩個角浮標下去，沿錨繩一路看到錨，錨繩中段各拍一張狀況照。自己的纜線不要跨過錨繩。這是箱網作業簽注的考核。",
      radio: {
        speaker: "林督導",
        start: "湧浪會讓你上下晃，那是正常的，不是你的錯。",
        done: "簽注下來了。你現在是養殖場會指名的駕駛員。",
        partial: "還差一點，等下一個平潮再考。"
      },
      deliverables: {
        east_buoy: "東南角浮標下方",
        east_line: "東南錨繩中段",
        east_anchor: "東南錨",
        west_buoy: "西南角浮標下方",
        west_line: "西南錨繩中段",
        west_anchor: "西南錨",
        recover: "回投放點回收"
      }
    }
  },
  grades: {
    none: {
      label: "學員（未持照）",
      short: "學員",
      opens: "公司內訓與水池檢查潛"
    },
    trainee: {
      label: "見習駕駛員",
      short: "見習",
      opens: "港內簡單檢查：碼頭 Level I、船殼、港內搜尋"
    },
    grade2: {
      label: "二級駕駛員",
      short: "二級",
      opens: "碼頭與船殼細部檢查、養殖場"
    },
    grade1: {
      label: "一級駕駛員",
      short: "一級",
      opens: "搜救、水庫、離岸風電（後續章節）"
    },
    senior: {
      label: "資深駕駛員",
      short: "資深",
      opens: "海纜、夜間、多機（後續章節）"
    },
    supervisor: {
      label: "主管",
      short: "主管",
      opens: "作業級任務的監看與指揮（後續章節）"
    }
  },
  endorsements: {
    aquaculture: {
      label: "箱網作業簽注"
    }
  },
  items: {
    laser_scaler: {
      label: "雷射比例尺",
      use: "兩道平行雷射點打在目標上，影像裡就有已知間距，可以量尺寸。",
      unlocks: "海生物厚度、缺陷尺寸等量測交付（Level II 工單）"
    },
    imaging_sonar: {
      label: "成像聲納",
      use: "能見度不足時以聲波成像找目標與結構，再用相機確認。",
      unlocks: "港內掉落物等搜尋工單"
    },
    cp_probe: {
      label: "陰極防蝕（CP）探針",
      use: "探針頂住鋼構，讀取對參考電極的電位，判斷防蝕是否足夠。",
      unlocks: "鋼板樁、鋼構的 CP 量測交付"
    },
    ut_gauge: {
      label: "超音波測厚儀（UT）",
      use: "探頭貼住鋼板量剩餘壁厚，找出腐蝕減薄處。",
      unlocks: "船殼與鋼構的測厚交付"
    },
    gripper: {
      label: "作業夾爪套件",
      use: "YX Model V 機械臂的作業夾爪與收集籃，回收類工單的標準配備。",
      unlocks: "死魚、掉落物等回收工單"
    },
    sticker_yx_logo: {
      label: "YX 公司標誌貼紙",
      use: "機身兩側的 YX 標誌。客戶在甲板上一眼就知道是誰家的機子。"
    },
    sticker_yx_stripe: {
      label: "YX 橘白塗裝條紋",
      use: "公司船隊的橘白斜紋，在混水裡比較好找。"
    }
  }
});

export const COPY = STRINGS;
