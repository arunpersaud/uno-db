<?php
/*
 * data-input.php --  this is part of a web interface for UNO-darmstadt
 *
 * Copyright 2009,2010,2011,2013 Arun Persaud
 *
 * ------------------------------------------------------------------------
 *
 * UNO-darmstadt is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or (at
 * your option) any later version.
 *
 * UNO-darmstadt is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see http://www.gnu.org/licenses/.  *
 *
 * ------------------------------------------------------------------------
 *
 *  wep-page:
 *     http://uno-darmstadt.sourceforge.net
 *
 *  It would be nice to get some feedback (bugs or other comments), so please drop
 *  me a line if you are using UNO-darmstadt :)
 *  have fun
 *        Arun
 */

include('config.php');
include('include/functions.php');

/*
 * open database
 */
$db = new mysqli($DB_HOST,$DB_USER, $DB_PASSWD, $DB_DB);
if ( $db->connect_errno )
  {
    echo "Failed to connect to Mysql ".$DB->connect_error." (".$DB->connect_errno.")\n";
    die("Couldn't connect to database");
  };

/* generate token */

/* todo add better token that has random bits in it, this one is good for a day...
 * not sure if token is needed at all or adds anything to the security, need to rethink this at one point
 */
$token = md5(date("z")."uno-admin by Arun");

if(myisset('token', 'what')) // and test for token
  {
    /* update DB */
    $newtoken = $_REQUEST['token'];
    $what = trim($_REQUEST['what']);

    switch($what){
    case 'locations':
      $id    = $_REQUEST['id'];
      $loc   = trim($_REQUEST['2']);
      $coord = trim($_REQUEST['3']);
      $time  = trim($_REQUEST['4']);

      if($coord!="")
	{
	  $coorde = explode(",",$coord);
	  $coordA = trim($coorde[0]);
	  $coordB = trim($coorde[1]);
	}

      /* validation */
      $ok=1;
      if($id && !is_numeric($id)) $ok=-1;
      if(!preg_match('/^[a-zA-Z0-9 ,?\']*$/',$loc)) $ok=-2;
      if(! (preg_match('/^[0-9-+.]*$/',$coordA) && preg_match('/^[0-9.+-]*$/',$coordB))) $ok=-3;
      if(! (preg_match('/^\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}:\d{2}$/',$time) || $time=="")) $ok=-4;

      if($ok==1)
	{
	  /* check if id exists */
	  $db_id = DB_query_array("SELECT id,create_date,name,X(coordinates),Y(coordinates) from locations where id=$id");
	  if ($db_id)
	    {
	      /* make backup of old value in extra db */
	      $backup = "location: id:".$db_id[0]." date:".$db_id[1]." name:".$db_id[2]." X:".$db_id[3]." Y:".$db_id[4];
	      DB_query("INSERT INTO backup VALUES (NULL, NULL, '$backup')");
	      /* change value */
	      DB_query("UPDATE locations SET create_date = ".DB_quote_smart($time)." WHERE id=$id");
	      DB_query("UPDATE locations SET name = ".DB_quote_smart($loc)." WHERE id=$id");
	      if($coord!="")
	      DB_query("UPDATE locations SET coordinates = ".
		       "POINT(".DB_quote_smart($coordA).",".DB_quote_smart($coordB).") WHERE id=$id");

	      echo "updated";
	    }
	  else
	    {
	      /* create new entry */
	      if($coord!="")
		DB_query("INSERT INTO locations VALUES (NULL, NULL, ".DB_quote_smart($loc).
			 ",POINT(".DB_quote_smart($coordA).",".DB_quote_smart($coordB)."))");
	      else
		DB_query("INSERT INTO locations VALUES (NULL, NULL, ".DB_quote_smart($loc).",NULL)");
	      echo "created";
	    }
	}
      else
	echo "incorrect input $ok, did not add new values";

      break;
    case 'players':
      $id = $_REQUEST['id'];
      $name = trim($_REQUEST['2']);
      $time = trim($_REQUEST['3']);

      /* validation */
      $ok=1;
      if($id && !is_numeric($id)) $ok=-1;
      if(!preg_match('/^[a-zA-Z0-9 ]*$/',$name)) $ok=-2;
      if(! (preg_match('/^\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}:\d{2}$/',$time) || $time=="")) $ok=-3;

      if($ok==1)
	{
	  /* check if id exists */
	  $db_id = DB_query_array("SELECT id,create_date,name from players where id=$id");
	  if ($db_id)
	    {
	      /* make backup of old value in extra db */
	      $backup = "players: id:".$db_id[0]." date:".$db_id[1]." name:".$db_id[2];
	      DB_query("INSERT INTO backup VALUES (NULL, NULL, '$backup')");
	      /* change value */
	      DB_query("UPDATE players SET create_date = ".DB_quote_smart($time)." WHERE id=$id");
	      DB_query("UPDATE players SET name = ".DB_quote_smart($name)." WHERE id=$id");

	      echo "updated";
	    }
	  else
	    {
	      /* create new entry */
	      if($time=="")
		DB_query("INSERT INTO players VALUES (NULL, NULL,".DB_quote_smart($name).")");
	      else
		DB_query("INSERT INTO players VALUES (NULL, ".DB_quote_smart($time).",".DB_quote_smart($name).")");
	      echo "created";
	    }
	}
      else
	echo "incorrect input $ok";

      break;
    case 'variations':
      $id = $_REQUEST['id'];
      $name  = trim($_REQUEST['2']);
      $short = trim($_REQUEST['3']);
      $time  = trim($_REQUEST['4']);

      /* validation */
      $ok=1;
      if($id && !is_numeric($id)) $ok=-1;
      if(!preg_match('/^[a-zA-Z0-9 ]*$/',$name)) $ok=-2;
      if(!preg_match('/^[a-zA-Z0-9 ]*$/',$short)) $ok=-3;
      if(! (preg_match('/^\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}:\d{2}$/',$time)||$time=="")) $ok=-4;

      if($ok==1)
	{
	  /* check if id exists */
	  $db_id = DB_query_array("SELECT id,create_date,name,short from variations where id=$id");
	  if ($db_id)
	    {
	      /* make backup of old value in extra db */
	      $backup = "variations: id:".$db_id[0]." date:".$db_id[1]." name:".$db_id[2]." short:".$db_id[3];
	      DB_query("INSERT INTO backup VALUES (NULL, NULL, '$backup')");
	      /* change value */
	      DB_query("UPDATE variations SET create_date = ".DB_quote_smart($time)." WHERE id=$id");
	      DB_query("UPDATE variations SET name  = ".DB_quote_smart($name)." WHERE id=$id");
	      DB_query("UPDATE variations SET short = ".DB_quote_smart($short)." WHERE id=$id");

	      echo "updated";
	    }
	  else
	    {
	      /* create new entry */
	      DB_query("INSERT INTO variations VALUES (NULL, NULL, ".
		       DB_quote_smart($name).",".
		       DB_quote_smart($short).")");
	      echo "created";
	    }
	}
      else
	echo "incorrect input $ok";

      break;
    case 'game':
      $variation = $_REQUEST['variation'];
      $location  = $_REQUEST['location'];
      $date      = trim($_REQUEST['date']);

      for($nplayer=0;myisset('player'.$nplayer); $nplayer++);
      for($ngames=0;myisset('game-'.$ngames.'-0'); $ngames++);

      /* check for end with black card */
      $ewbc = array();
      for($i=0; $i<$ngames; $i++)
	$ewbc[$i] = myisset('ewbc'.$i);

      /* find player ids */
      $players = array();
      for($i=0; $i<$nplayer; $i++)
	$players[$i] = $_REQUEST['player'.$i];

      /* validation */
      $ok=1;
      if(!is_numeric($variation)) $ok=-1;
      if(!is_numeric($location)) $ok=-2;
      if(!preg_match('/^\d{4}-\d{2}-\d{2}$/',$date)) $ok=-3;

      /* players id needs to be a number */
      for($i=0; $i<$nplayer; $i++)
	if(!is_numeric($players[$i])) $ok=-4;

      /* game result needs to be a number or "-", each game needs to have exactly one "-" */
      for($j=0; $j<$ngames; $j++)
	{
	  $gotwinner=0;
	  for($i=0; $i<$nplayer; $i++)
	    {
	      if(!preg_match('/^[0-9\-]*$/', $_REQUEST['game-'.$j.'-'.$i])) $ok=-5;
	      if($_REQUEST['game-'.$j.'-'.$i]=="-")
		$gotwinner++;
	    }
	  if($gotwinner!=1) $ok=-5.5;
	}

      /* player id can only show up once */
      for($i=0; $i<$nplayer; $i++)
	for($j=$i+1; $j<$nplayer; $j++)
	  if($players[$i]==$players[$j]) $ok=-6;

      /* ids of location, variations and players must exist */
      for($i=0; $i<$nplayer; $i++)
	{
	  $db_id = DB_query_array("SELECT id from players where id=".$players[$i]);
	  if (!$db_id) $ok=-7;
	};
      $db_id = DB_query_array("SELECT id from variations where id=$variation");
      if (!$db_id) $ok=-7;
      $db_id = DB_query_array("SELECT id from locations where id=$location");
      if (!$db_id) $ok=-7;

      if($ok==1)
	{
	  /* everything ok, submit to database */

	  /* create session */
	  //echo "INSERT INTO session VALUES (NULL, $date, $location, $nplayer, NULL, $variation) <br/>";
	  DB_query("INSERT INTO session VALUES (NULL, ".DB_quote_smart($date).", ".
		   DB_quote_smart($location).", ".
		   DB_quote_smart($nplayer).", CURRENT_TIMESTAMP, ".
		   DB_quote_smart($variation).")");
	  $session_id = DB_insert_id();

	  /* keep track of score, since we need to calculate the differences for each single score */
	  for($j=0; $j<$nplayer; $j++)
	    $lastscore[$j]=0;

	  /* create games */
	  for($i=0;$i<$ngames; $i++)
	    {
	      /* create game id */
	      //echo "INSERT INTO games VALUES (NULL, $session_id, ".$ewbc[$i]." ) <br />";
	      DB_query("INSERT INTO games VALUES (NULL, ".
		       DB_quote_smart($session_id).", ".
		       DB_quote_smart($ewbc[$i])." )");
	      $game_id = DB_insert_id();

	      for($j=0; $j<$nplayer; $j++)
		{
		  $score = $_REQUEST['game-'.$i.'-'.$j];
		  /* mark winner */
		  if($score=="-")
		    $score = -9999;
		  else
		    $score = $score - $oldscore[$j];

		  DB_query("INSERT INTO scores VALUES (NULL, $game_id, ".
			   DB_quote_smart($players[$j]).",".
			   DB_quote_smart($score).", $j )");
		  //echo " game $i: position: $j player:".$players[$j]." score: $score <br/>";

		  /* remember old score */
		  if($score!=-9999)
		    $oldscore[$j] = $_REQUEST['game-'.$i.'-'.$j];

		}
	    }

	  echo "submitted to database";
	}
      else
	echo "Validation error: $ok";

      break;
    }
  }
else
  {
    //output html
    // check tmp.tmp to see what needs to be implemented
    output_header();
?>

<p>After changing/adding locations or players names you need to reload to be able to use them in the game input!</p>
<p>There is some error checking on the input, but double check before you hit "save" or "submit".</p>
<p>Entering coordinates is not supported at the moment (field needs to be empty).</p>

<ul class="datainput">
<li class="locations"> <button class="toggle">show/edit locations</button>
<?php
	 echo "<table class=\"stats\">\n";
	 echo "<thead><tr><th>ID</th><th>Name</th><th>Coordinates</th><th>created</th><th></th></tr></thead>\n";
	 echo "<tbody>\n";
         $datatmp = DB_query_array_all("SELECT id,create_date,name,X(coordinates), Y(coordinates) FROM locations ORDER BY name");
	 foreach($datatmp as $dat)
	   {
	     $id     = $dat[0];
	     $date   = $dat[1];
	     $name   = $dat[2];
	     $coorX  = $dat[3];
	     $coorY  = $dat[4];
	     echo "<tr><td>$id</td> <td>$name</td><td>$coorX $coorY</td> <td>$date</td> <td><button class=\"edit\">edit</button></td></tr>\n";
	   }
	 echo "<tr><td></td> <td></td><td></td> <td></td> <td><button class=\"edit\">new</button></td></tr>\n";
	 echo "</tbody></table>\n";
?>
<li class="players"> <button class="toggle">show/edit players</button>
<?php
	 echo "<table class=\"stats\" >\n";
	 echo "<thead><tr><th>ID</th><th>Name</th><th>created</th><th></th></tr></thead>\n";
	 echo "<tbody>\n";
         $datatmp = DB_query_array_all("SELECT * FROM players ORDER BY name");
	 foreach($datatmp as $dat)
	   {
	     $id = $dat[0];
	     $date  = $dat[1];
	     $name  = $dat[2];
	     echo "<tr><td>$id</td> <td>$name</td> <td>$date</td> <td><button class=\"edit\">edit</button></td></tr>\n";
	   }
	 echo "<tr><td></td> <td></td><td></td> <td><button class=\"edit\">new</button></td></tr>\n";
	 echo "</tbody></table>\n";
?>
<li class="variations"> <button class="toggle">add/edit variations </button>
<?php
	 echo "<table class=\"stats\" >\n";
	 echo "<thead><tr><th>ID</th><th>Name</th><th>short</th><th>created</th><th></th></tr></thead>\n";
	 echo "<tbody>\n";
         $datatmp = DB_query_array_all("SELECT * FROM variations");
	 foreach($datatmp as $dat)
	   {
	     $id    = $dat[0];
	     $date  = $dat[1];
	     $name  = $dat[2];
	     $short = $dat[3];
	     echo "<tr><td>$id</td> <td>$name</td> <td>$short</td> <td>$date</td> <td><button class=\"edit\">edit</button></td></tr>\n";
	   }
	 echo "<tr><td></td> <td></td> <td></td> <td></td> <td><button class=\"edit\">new</button></td></tr>\n";
	 echo "</tbody></table>\n";
?>
<li class="game"> <button class="gametoggle">add game</button>
<form action="data-input.php" method="post">
<input type="hidden" name="token" value="<?php echo $token; ?>">
<input type="hidden" name="what"  value="game">
<label for="variation"> Variation:</label> <select name='variation' id='variation'>
<?php
 $datatmp = DB_query_array_all("SELECT id,name FROM variations",MYSQLI_ASSOC);
 foreach ($temp = $datatmp as $temp)
  {
    echo "<option value='".$temp['id']."'>".$temp['name']."</option>\n";
  }
?>
</select><br />
<label for="location"> Location:</label> <select name='location' id='location'>
<?php
 $datatmp = DB_query_array_all("SELECT id,name FROM locations",MYSQLI_ASSOC);
 foreach($datatmp as $temp)
  {
    echo "<option value='".$temp['id']."'>".$temp['name']."</option>\n";
  }
?>
</select> <br />
<label for="date"> Date:</label><input type='date' name='date' id='date' placeholder='yyyy-mm-dd'>
<p>Input running totals! Mark winner with a "-"</p>
<table class="stats">
<thead>
  <tr><th>End with black card</th> <th><button class="newplayer">new player</button></th></tr>
</thead>
<tbody>
  <tr> <td><input type="checkbox" name="ewbc0" value="ewbc" /></td> <td><button class="newgame">new row</button></td> </tr>
</tbody>
</table>
<input type="submit" value="Submit" />
</form>

</ul>

<script>

/* gives a selector with all possible names */
function printselectplayer(i) {
   var html = "<select name=\"player"+(i-2)+"\">\n";
<?php
   $datatmp = DB_query_array_all("SELECT id,name FROM players ORDER BY name ASC",MYSQLI_ASSOC);
 foreach($datatmp as $temp)
  {
    echo 'html += "<option value=\''.$temp['id']."'>".$temp['name']."</option>\\n\";\n";
  }
?>
   html += "</select>\n";
   return html;
 }

var token = <?php echo '"'.$token.'"' ?> ;

</script>

<?php
output_footer();
  } // end if-else html output
?>
